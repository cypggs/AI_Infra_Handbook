# 5. 核心模块

> 一句话理解：把第 3 章的架构拆成可实现的零件——七个模块各司其职，其中前缀索引与 block 池决定「能不能复用」，传输引擎与分层管理器决定「复用贵不贵」，路由与观测决定「复用率稳不稳」。

## 5.1 Block Manager（块管理器）

职责：KV block 的分配、映射、共享、逐出。对应 vLLM 的 `BlockManager`、SGLang 的 `RadixCache` 底层。

核心机制（Mini Demo 的 `block.py` 逐项模拟）：

- **分配**：逻辑 token 位置按 block_size 切分映射到物理 block；分配失败触发逐出；
- **引用计数**：每条请求持有 block 引用，请求结束引用减一；
- **Copy-on-Write**：beam search / 并行采样 fork 出的分支共享 block，写入时复制，保证共享零拷贝、写入隔离；
- **LRU 逐出**：引用计数归零的 block 进入逐出候选，被新请求按 LRU 顺序回收。

设计要点：block_size 是碎片率与索引开销的权衡——太大则内部碎片多（平均浪费 block_size/2 个 token 的显存），太小则 radix tree 与哈希表条目膨胀；16-32 token 是常见甜点。

## 5.2 Prefix Radix Tree（前缀索引树）

职责：回答「这条 token 序列命中缓存到哪一段」。对应 SGLang RadixAttention、vLLM prefix caching 的哈希索引。

- 按 token 序列（而非请求）组织，任意两条请求的公共前缀只存一份；
- 插入即分裂：分叉处把 segment 切成「公共段 + 各自尾巴」；
- 逐出按叶子 LRU：公共祖先保留，只删最久未访问的分支（Mini Demo 的 `prefix.py` 实现完整插入/分裂/逐出）。

生产细节：真实系统按 block 粒度对齐（token 数须为 block_size 的倍数），且节点上挂的不只是 token 段，还有 block id 列表、引用计数、分层位置（L1/L2/L3）等元数据。

## 5.3 Transfer Engine（传输引擎）

职责：跨节点搬运 KV block，是 PD 分离的承重墙。对应 Mooncake Transfer Engine、NVIDIA NIXL。

关键能力：

| 能力 | 说明 | 实测参考 |
|---|---|---|
| 拓扑感知选路 | 优先 NVLink > 同机 PCIe > RDMA > TCP | Mooncake TE 支持 NVLink/RDMA/TCP/EFA 等多后端 |
| 多流聚合 | 多条 RDMA QP / 多网卡并行 | 8×400Gbps RoCE 下 Mooncake TE 达 ~190 GB/s |
| 批量异步 | 提交一批 block 传输不阻塞引擎主循环 | 零拷贝、单/多 QP 批量提交 |
| 故障切换 | 链路中断自动换路 | TE 内置重试与切换 |

性能锚点：单条 200 Gbps 链路有效带宽约 20+ GB/s，而 40 GB 的 128K 上下文 KV 只需约 2 秒——**传输不是瓶颈，调度才是**。

## 5.4 Cache-Aware Router（缓存感知路由）

职责：在集群尺度放大复用率。对应 Dynamo Smart Router、SGLang cache-aware LB、Gateway API Inference Extension 的 EPP。

- **输入**：请求前缀哈希、各实例缓存事件（block 注册/逐出）、实例负载；
- **打分**：命中长度加分，队列深度 / 负载减分；
- **防热点**：命中分必须乘以衰减系数，否则所有同前缀请求挤爆单实例；
- **两级路由**：Gateway 粗选池子（前缀分片），池内细选实例（精确命中 + 负载）。

## 5.5 Tier Manager（分层管理器）

职责：决定 block 的驻留层级与上下迁移。对应 LMCache、Dynamo KV Block Manager、SGLang HiCache Manager。

- **降级（demote）**：GPU 水位高 → 冷 block 沉 CPU；CPU 满 → 沉 SSD；全满才丢；
- **提升（promote）**：慢层命中时读回 GPU，收益大于成本才做（第 2 章不等式）；
- **异步搬运**：迁移走独立线程/协程，不阻塞 decode 主循环；
- **变换管线**：搬运途中可插入压缩/量化（FP8 KV、token dropping，经 LMCache SERDE 这类插件接口）。

## 5.6 KV Quantizer（量化器）

职责：压缩 KV 的每 token 占用。与 [AI 编译器](/04-llmops/ai-compiler/)主题的 kernel 优化直接相关。

- **FP8 KV**：占用减半，配合 FlashMLA / FlashInfer 的 FP8 kernel，质量损失通常在可接受范围（ DeepSeek 系列模型在 vLLM 中以 MXFP8 存储 whole KV 就是一例）；
- **INT4 / 更低**：占用减到 1/4，但对长上下文注意力质量影响明显，多用于对质量不敏感的长前缀缓存；
- **分层量化**：热数据 FP16、冷数据 FP8——「时间换空间」的细粒度版本。

量化收益要计入迁移成本：量化后的 block 更小，传输与分层搬运同步变快——两个红利叠加。

## 5.7 Observability（可观测性）

KV 缓存层的专属指标（常被忽略但排障必需）：

| 指标 | 定义 | 异常信号 |
|---|---|---|
| prefix 命中率 | 命中 token 数 / 输入 token 总数 | 骤降 → 路由亲和失效或逐出过狠 |
| 各层命中率 | GPU/CPU/SSD 各自命中占比 | SSD 命中高但 TTFT 涨 → 提升策略太激进 |
| 逐出/下沉速率 | blocks/s | 持续高企 → 容量不足，在反复搬运 |
| 传输带宽利用率 | 实际/理论 RDMA 带宽 | 低 → 调度没喂饱链路 |
| 缓存失效率 | 路由预测命中但实际未命中 | 高 → 全局索引滞后严重 |

## 小结

- Block Manager 与 Radix Tree 是「能不能复用」的地基：引用计数 + COW + 叶子 LRU 逐出。
- Transfer Engine 与 Tier Manager 决定「复用贵不贵」：流水线、多流、异步下沉、量化变换。
- Router 与 Observability 决定「复用率稳不稳」：加权打分防热点，专属指标防劣化。
