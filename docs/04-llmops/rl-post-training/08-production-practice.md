# 8. 企业生产实践

## 一句话理解

> RL Post-Training 的生产实践，本质上是**用预算与算力换模型能力上限**的工程博弈。DeepSeek、字节、阿里、Kimi、NVIDIA 的选择各不相同，但都在回答同样的问题：Rollout 给多少卡？Train 给多少卡？同步怎么做？长尾怎么治？

## DeepSeek-R1：纯 RL 涌现推理能力

### 训练规模

- **基础模型**：DeepSeek-V3-Base（671B MoE，激活 37B）
- **算法**：GRPO（无 Critic 网络）
- **奖励**：纯可验证奖励（数学 + 代码）
- **集群**：H800 GPU（具体规模未公开，估算 512-2048 卡）

### 关键工程决策

1. **GRPO 替代 PPO**：去掉 Critic，节省一半显存。代价是每个 prompt 要生成 G=64 个 response。
2. **可验证奖励替代 Reward Model**：数学用 sympy 比对、代码跑测试，完全不需要部署 RM 服务。
3. **长度激励**：奖励函数包含长度项，鼓励模型生成更长的 chain-of-thought。
4. **两阶段**：
   - **R1-Zero**：直接在 Base 模型上纯 RL，涌现推理能力但输出难读（中英混杂）。
   - **R1**：先 SFT 冷启动（几千条高质量 CoT 数据），再 RL，解决可读性。

### 性能数据（公开）

| 指标 | R1-Zero | R1 |
|---|---|---|
| AIME 2024 pass@1 | 71.0% | 79.8% |
| MATH-500 pass@1 | 95.9% | 97.3% |
| CodeForces rating | 1444 | 2029 |

### 工程洞察

- **"Aha moment"**：训练到 ~8000 step 时，模型自发学会"等等，让我重新想想"（反思能力），这是 RL 涌现的标志性事件。
- **长度自增长**：训练过程中，平均 response 长度从几百 token 自发增长到几千 token，说明 RL 在鼓励"想更多"。

## 字节 Seed：veRL 框架与 Agentic RL 矩阵

### 开源情况

veRL 于 2024 年底开源，是字节 Seed 团队 RL 训练的生产框架，支撑了豆包大模型。截至 2026-10 已迭代到 v0.9.1（2026-09-20）。

### 核心特性（v0.9 视角）

1. **V1 trainer 三模式**：sync / colocate_async / separate_async 统一配置，separate_async 可把训练侧空闲 GPU 借给生成侧。
2. **Server-based rollout**：v0.7 起移除 SPMD rollout，Rollout 是独立在线服务，支持 vLLM PD 分离与可插拔路由。
3. **权重增量化**：`delta_sharded` checkpoint engine（72B 实测 3.1 倍），NCCL/NIXL/TorchTitan 多传输后端。
4. **算法覆盖**：PPO / GRPO / GSPO / DAPO / CISPO / SAPO，On-Policy Distillation 端到端（v0.8）。

### 生产实践

- **规模**：单任务千卡级
- **Rollout:Train 比例**：动态调整，长推理任务 Rollout 占 70-80%
- **权重同步**：同卡场景零拷贝，异卡场景走 checkpoint engine（delta 分片 + FP8/MXFP4）
- **故障恢复**：Ray Actor 自动重启 + checkpoint 定时保存

### Agentic RL 实践（2026）

- **CUDA-Agent**（与清华 AIR，2026-08 公开，arXiv:2602.24286）：在真实 CUDA 开发沙箱里对 Seed1.6（230B MoE）做 PPO 训练（150 step、131k 上下文），用"正确性 + 性能"的离散里程碑奖励 + 多重反 hacking 设计；KernelBench 250 题上 98.8% 正确率、几何平均加速 2.11 倍，超过 torch.compile 的比例达 96.8%。
- **Seed-Prover 1.5**：Lean 形式化证明的 Agentic RL——模型在证明过程中调用 Lean 工具、从成败经验中学习，PutnamBench 达 88%。

启示：**当环境反馈足够可靠（编译器、证明器、profiler），Agentic RL 的奖励可以完全由环境给出**，不再需要人工标注或 RM。

## 阿里 Qwen：GSPO 与 Agentic RL

### Qwen3 训练

- **算法**：GSPO（Group Sequence Policy Optimization，GRPO 的改进版）
- **改进点**：把 token-level importance sampling 改为 sequence-level，解决长序列训练不稳定。
- **Agentic RL**：在 Qwen3-Coder 上大规模使用 Agentic RL，让模型在真实终端/浏览器中学习。

### ROLL 框架

阿里内部框架，专门优化 Agentic RL：

- **环境池**：维护大量并发环境（终端、浏览器、代码执行器）。
- **异步 Rollout**：环境延迟长，必须异步。
- **Replay Buffer**：环境交互宝贵，样本会复用。

### 工程亮点

- **Agentic 环境沙箱**：基于 gVisor 的安全沙箱，支持上千并发。
- **长 Horizon 训练**：单个 episode 长达上百轮工具调用，对 Experience Buffer 设计挑战极大。

## 蚂蚁 + 清华：AReaL 全异步路线

### 演进时间线

- **v1.0（2026-03-04）**：Proxy Worker 设计——Agent 侧只改 API endpoint 即可接入 RL 训练；相对同步系统报告 2.77 倍提速。
- **KPop / IcePop（2026-06）**：基于双向二元 KL / importance ratio 的 token 掩码，修正异步训练的偏差。
- **2.0（2026-07-01）**：微服务化——训练 / 推理 / Agent / 权重更新四个独立服务，内置 Hermes 在线 RL loop 与端到端 SWE RL 示例；2026-01 起支持昇腾 NPU。

### 工程启示

AReaL 证明了**"框架"可以没有中心节点**：当四个服务通过队列与版本协议解耦后，Agentic RL 的环境部署可以分散到离数据源最近的地方（代码仓旁、浏览器集群旁），训练集群只管消费样本。

## Kimi K3：百万 token Agentic RL（2026-07）

### 训练规模

- **基础模型**：Kimi K3（2.8T 总参数 MoE，激活 104B，1M 上下文）
- **后训练流程**：SFT → 多领域 RL（通用 / Agentic / 代码，多个推理努力档位）→ 多教师 On-Policy Distillation
- **技术报告**：arXiv:2607.24653（2026-07）

### 工程特点

- **超长上下文训练**：1M 上下文的 Agentic RL 对 KV Cache 与轨迹存储是极端压力测试，需要 rollout 状态外置与续跑能力。
- **AgentENV 沙箱**（与 kvcache-ai 开源）：Firecracker microVM，快照恢复小于 50ms、单个环境可 fork 出 16 个子环境——长程任务（数百次工具调用）的环境状态可以被挂起、复制、恢复。
- **多教师 OPD**：RL 之后用多个教师模型做在线蒸馏，复用同一套 rollout 基建（这也解释了为什么 veRL v0.8 把 On-Policy Distillation 做成一等公民）。

### 与前代 K2 的对比

| 维度 | K2（2025） | K3（2026-07） |
|---|---|---|
| 参数 | 1T MoE / 32B 激活 | 2.8T MoE / 104B 激活 |
| 上下文 | 256k | 1M |
| RL 场景 | 代码、搜索、工具 | + 长程软件工程 / kernel / 通用 Agent |
| 环境 | 内置工具 | AgentENV 沙箱平台（开源） |
| 后训练收尾 | 直接 RL | RL + 多教师 On-Policy Distillation |

## Agentic RL 的沙箱基础设施（2026 新战场）

Agentic RL 让"环境"从评分脚本升级为**沙箱平台**，这是 2026 年最重要的基建变化：

| 平台 | 出品方 | 关键数字 / 机制 |
|---|---|---|
| **DSec** | DeepSeek（arXiv:2609.22978，2026-09） | 单生产单元约 160 节点；日产约 300 万沙箱；峰值 38 万并发；每秒 5000+ 创建；FnCall / 容器 / microVM / 全 VM 四种后端；镜像从 3FS 分布式文件系统按需加载 |
| **AgentENV** | Moonshot + kvcache-ai（开源） | Firecracker microVM；快照恢复小于 50ms；单环境 fork 16 子环境；支撑 K3 百万 token 训练 |
| **NeMo Gym / Harbor / OpenEnv** | NVIDIA / 社区 | 环境接口标准化（OpenEnv 走 Gymnasium-over-HTTP），让框架无关地接入 RL 训练 |

### DSec 与 RL 框架的协同设计

- **有状态 rollout 与可抢占训练分离**：GPU 训练可以被抢占/回收，而沙箱里的环境会话（文件系统、进程、网络状态）被保留，资源恢复后续跑。
- **四层隔离按需选择**：纯函数调用（FnCall）零开销，容器秒级，microVM 强隔离，全 VM 兼容遗留环境——按任务的隔离需求路由。
- **反 reward hacking**：平台层记录环境真实状态，防止 agent 通过篡改环境骗取奖励。

HuggingFace 2026 年的调研（"One sandbox per rollout"）把这套模式总结为行业标准：**每个 rollout 一个沙箱，环境生命周期由独立平台管理，RL 框架只负责采样与训练**。

## NVIDIA NeMo-RL：硬件-软件协同

### 设计目标

深度整合 NVIDIA 全栈：TensorRT-LLM 推理 + Megatron 训练 + NVLink 互联。

### 核心特性

- **TensorRT-LLM Rollout**：极致推理性能（CUDA graph、FP8）。
- **Megatron 训练**：与预训练同一套并行策略。
- **NVLink 权重同步**：在同 NVLink domain 内直传，绕过网卡。

### 适用场景

- **NVIDIA 全栈用户**：已有 TensorRT-LLM 推理部署的团队。
- **超大规模**：万卡级训练，需要 NVLink 高带宽。

## Meta Llama 4：RLHF + RLVR 组合

### 训练流程

1. **Pre-training**：40T tokens
2. **Mid-training**：长上下文扩展
3. **SFT**：指令微调
4. **RLHF**：基于 Reward Model 的人类偏好对齐
5. **RLVR**：数学/代码的可验证奖励

### 工程特点

- **双 Reward 系统**：Reward Model + Verifiable Reward 同时使用。
- **多任务混合**：通用对话 + 数学 + 代码 + 推理，按权重混合训练。

## 工程最佳实践提炼

### 1. Rollout 资源配比经验值

| 任务类型 | 平均生成长度 | Rollout 占比 | Train 占比 |
|---|---|---|---|
| 通用对话（RLHF） | 500-1k token | 40-50% | 50-60% |
| 数学/代码（RLVR） | 1k-4k token | 60-70% | 30-40% |
| 长推理（R1 类） | 4k-16k token | 70-80% | 20-30% |
| Agentic RL | 多轮交互 | 80-90% | 10-20% |

### 2. 常见故障与对策

| 故障现象 | 可能原因 | 对策 |
|---|---|---|
| Reward 突然飙升后崩溃 | Reward hacking | 加可验证奖励 + KL penalty |
| Response 长度急剧下降 | Length collapse | 加长度奖励项 / 调低 temperature |
| KL 爆炸（>50） | 学习率过高 / clip 太松 | 降 LR / 收紧 clip / 提高 β |
| Rollout 长尾严重 | 长度方差大 | Continuous Batching + 长度分桶 |
| 权重同步超时 | 网络带宽不足 | 量化传输 / 增量同步 / 拓扑优化 |
| 训练 loss NaN | 梯度爆炸 | Gradient clipping + BF16 loss scale |

### 3. 性能调优清单

- [ ] **Rollout**
  - [ ] 开启 vLLM V1 Prefix Caching（同一 prompt 的 group 共享 KV）
  - [ ] Continuous Batching + chunked prefill
  - [ ] 大规模场景评估 PD 分离（prefill / decode 分池）
  - [ ] Agentic 场景接入 server-based rollout + 可插拔路由
  - [ ] Sampling 用 `temperature=1.0, top_p=1.0` 保证探索
  - [ ] KV cache offload 到 CPU/NVMe（长上下文场景）

- [ ] **Train**
  - [ ] Megatron TP=8, PP=4, DP=N
  - [ ] FlashAttention 3
  - [ ] Gradient Checkpointing
  - [ ] BF16 + FP32 master weight

- [ ] **权重同步**
  - [ ] 优先 NCCL / NIXL 直传
  - [ ] delta 分片增量同步（delta_sharded 类方案）
  - [ ] FP8 / MXFP4 量化传输
  - [ ] 流水线 save/load

- [ ] **异步与陈旧性**
  - [ ] 逐样本 weight_version 打标
  - [ ] 缓冲队列深度上界（如 lag ≤ 2）
  - [ ] 超龄样本丢弃或 TIS 修正
  - [ ] 监控样本丢弃率与平均 lag

- [ ] **Reward 与沙箱**
  - [ ] 可验证奖励优先于 Reward Model
  - [ ] 混合奖励防 hacking
  - [ ] 沙箱平台化（DSec / AgentENV 类），支持快照恢复与续跑
  - [ ] 环境侧记录真实状态，防环境篡改型 hacking

### 4. 监控指标

| 指标 | 健康 | 告警 |
|---|---|---|
| reward_mean | 缓慢上升 | 突然飙升 / 骤降 |
| kl_divergence | 1-10 | >50 |
| response_length_mean | 稳定或缓升 | 急剧下降 |
| ratio_clip_frac | 5-20% | >50% |
| rollout_throughput_tps | 稳定 | 持续下降 |
| train_mfu | >35% | <20% |

## 本章小结

- **DeepSeek-R1**：纯 GRPO + 可验证奖励，证明了 RL 涌现推理能力的可行性；2026 年的 DSec 把沙箱做成了日产 300 万的基础设施。
- **字节 Seed**：veRL v0.9（V1 trainer 三模式 + server-based rollout + delta 权重）+ CUDA-Agent / Seed-Prover 的"环境即奖励"实践。
- **阿里 Qwen**：GSPO + Agentic RL；蚂蚁/清华 AReaL 2.0 走微服务全异步路线。
- **Kimi K3**：2.8T MoE + 1M 上下文 + AgentENV 沙箱 + 多教师 OPD，把 Agentic RL 推到百万 token 长程。
- **共同经验**：Rollout 占大头、可验证奖励优先、KL 惩罚必须、长尾要治理、监控要细；2026 年新增——异步化必须有陈旧性控制，环境必须平台化。

下一章我们把这些经验提炼为可执行的最佳实践。
