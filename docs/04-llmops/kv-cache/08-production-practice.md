# 8. 企业生产实践

> 一句话理解：生产级的 KV 缓存部署都是「成本工程」——Mooncake 用闲置 CPU/SSD 换 GPU 利用率，DeepSeek 用 3FS 换 DRAM 容量，Dynamo 用 SLA 驱动自动扩缩，共同目标是在不违约 SLO 的前提下把每一分 prefill 计算都省下来。

## 8.1 Mooncake @ Kimi：KVCache-centric 的分离架构

**背景**：Kimi 的长上下文（最高 2M 级）+ 高并发 chat 负载，prefill 与 decode 资源争抢严重。

**架构决策**（OSDI'24 论文 + 开源实现）：

- prefill/decode 彻底分离，各自独立扩缩；
- GPU 集群中闲置的 CPU、DRAM、SSD 组成 KVCache 资源池，Transfer Engine 负责跨层搬运；
- 以 KV 为中心调度：路由优先前缀亲和，planner 按负载在 P/D 池间搬请求。

**效果**（论文与官方数据）：

- 生产 trace 上满足同等 SLO 多承载约 75% 请求；
- 长上下文场景单用户 decode 吞吐 525 tokens/s；
- Kimi K2 在 128×H200 集群上报 224k tokens/s prefill、288k tokens/s decode；
- Transfer Engine 在 4×200Gbps RoCE 下达 ~87 GB/s、8×400Gbps RoCE 达 ~190 GB/s。

**经验**：把「缓存放哪」当成调度问题而非存储问题——闲置资源池化 + 拓扑感知传输，比单纯加 GPU 便宜一个数量级。

## 8.2 DeepSeek 3FS：SSD 作为 KV 缓存层

**背景**：推理集群的 KV 缓存需求超过 DRAM 容量，需要一个比 DRAM 便宜、比对象存储快的中间层。

**方案**（MIT 开源）：

- 聚合集群内数千块 NVMe SSD 的带宽，应用 locality-oblivious 访问；
- CRAQ 链式复制保证强一致，FoundationDB 存元数据；
- KVCache 客户端作为推理侧接入层，官方测试集群峰值读 ~40 GiB/s。

**适配要点**：

- KV block 按条带化分布在多 SSD 上，单 block 读取聚合多盘带宽；
- 与 Mooncake Store 的对象存储后端对接，成为分层缓存的最底层；
- 参考 [DeepSeek 案例](/09-case-study/deepseek/)主题了解其训练侧（GraySort、checkpoint）复用同一套存储底座的设计哲学：**一套存储系统同时服务训练数据、checkpoint 与推理 KV**。

## 8.3 NVIDIA Dynamo：SLA 驱动的集群编排

**背景**：企业需要在异构引擎（SGLang/TensorRT-LLM/vLLM）与异构拓扑（NVL72、多机架）上统一做 PD 分离。

**生产形态**（1.5.1）：

- **Smart Router**：KV 重合度 + 负载打分，减少重复 prefill；
- **Planner**：以 TTFT/ITL 为 SLA 目标自动调整 P/D 池规模——白天 prefill 重扩 P 池，晚高峰 decode 重扩 D 池；
- **KV Block Manager**：GPU→CPU→SSD→S3/Azure Blob 四级卸载（SGLang 侧仍标实验中）；
- **Grove 算子**：NVL72 机架/NUMA 感知调度，KV 传输走 NVLink 域优先。

**经验**：当集群规模上来后，**缓存策略的敌人不是带宽而是碎片**——请求长度分布越杂，block 池碎片化越严重，Planner 的池间迁移 + KVBM 的规整能力比任何单点优化都值钱。

## 8.4 SGLang HiCache：引擎内一站式分层

**背景**：用户不想引入外部缓存系统，希望引擎自带分层能力。

**形态**（v0.5.21）：

- L1 GPU → L2 CPU/NVMe → L3 远端（Mooncake Store / 可动态挂载卸载的存储）；
- 统一 radix tree 管理全部层级的前缀索引，Rust 核心保证查找性能；
- 会话感知逐出（`--enable-session-radix-cache`）保护活跃会话的前缀不被驱逐；
- SWA 分支缓存让滑动窗口模型的命中率从 43.8% 提到 60.8%，平均 TTFT 从 1.57s 降到 1.07s。

**经验**：引擎内分层的优势是零外部依赖、索引一致性好；劣势是缓存资产与引擎进程绑定，进程崩溃即丢失（这正是 LMCache「no fate-sharing」瞄准的痛点）。生产上两者常组合使用：HiCache 管热数据，Store 管冷数据。

## 8.5 部署形态速查

| 规模 | 推荐形态 | 组件 |
|---|---|---|
| 单实例 ~ 几实例 | 引擎内 prefix caching | vLLM/SGLang 原生开关 |
| 中小集群（< 32 GPU） | PD 分离 + LMCache | vLLM + LMCache connector |
| 大集群（百卡级） | Mooncake 全套 / Dynamo | TE + Store + Planner |
| 超长上下文 / 高复用负载 | + SSD/3FS 底层 | 上述 + 3FS / HiCache L3 |

## 8.6 容量规划实例

为一个 32×H100 推理集群做 KV 容量规划（示意）：

```text
模型：70B 类 GQA，FP8 KV → 160 KiB/token
单卡 H100 80 GB：权重 FP8 ~70 GB → KV 池 ~6 GB/卡 → 单实例(TP8) KV 池 48 GB
GPU 层容量：48 GB / 160 KiB ≈ 30 万 token（集群 8 实例 ≈ 240 万 token 热缓存）
CPU 层：每节点 2 TB DRAM → 集群 ~64 TB ≈ 4 亿 token（约 GPU 层的 170 倍）
SSD 层：每节点 8×4 TB → 集群 ~1 PB（再扩 16 倍）
```

结论：分层之后「缓存能装下多少上下文」从显存问题变成成本问题——**每一层的成本差一个数量级，命中率随层数递减，规划的核心是各层水位与降级速率**。

## 小结

- Mooncake：分离 + 资源池化，用闲置 CPU/SSD 换 GPU 利用率，75% 请求增量是行业标杆数字。
- 3FS：把 SSD 集群变成 KV 缓存层，40 GiB/s 读证明「SSD 缓存」不是纸面概念。
- Dynamo：SLA 驱动的 P/D 池自动扩缩 + 四级卸载，代表「编排层」的成熟。
- SGLang HiCache：引擎内一站式分层，与外部 Store 组合是生产常态。
