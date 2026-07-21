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

## 字节 Seed：veRL 框架

### 开源情况

veRL 于 2024 年底开源，是字节 Seed 团队 RL 训练的生产框架，支撑了豆包大模型。

### 核心特性

1. **HybridEngine**：同一组 GPU 上时分复用 vLLM 和 FSDP，显存利用率最高。
2. **灵活拓扑**：支持 Co-located / Disaggregated / Hybrid 三种部署模式。
3. **模块化**：Reward / Algorithm / Rollout 都可插拔。

### 生产实践

- **规模**：单任务千卡级
- **Rollout:Train 比例**：动态调整，长推理任务 Rollout 占 70-80%
- **权重同步**：同卡场景零拷贝，异卡场景用 NVMe over Fabrics
- **故障恢复**：Ray Actor 自动重启 + checkpoint 定时保存

### 关键技术点

- **3D-HybridEngine**：把 vLLM 的 TP 并行维度与 FSDP 的 DP/TP 维度对齐，让权重可以零拷贝在两者之间传递。
- **动态负载均衡**：根据当前 batch 的 prompt 长度分布，动态调整 Rollout worker 数量。

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

## Kimi K2：大规模 Agentic RL

### 训练规模

- **基础模型**：Kimi K2（1T 总参数 MoE，激活 32B）
- **算法**：未公开具体细节，推断为 GRPO 变种
- **场景**：大规模 Agentic RL，覆盖代码、搜索、工具使用

### 工程特点

- **超长上下文**：K2 支持 256k context，RL 训练时长上下文 KV Cache 是巨大挑战。
- **工具集成**：内置 code execution、web search、file system 等工具。
- **Muon 优化器**：使用自研 Muon 优化器，比 AdamW 更稳定。

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
  - [ ] Sampling 用 `temperature=1.0, top_p=1.0` 保证探索
  - [ ] KV cache offload 到 CPU/NVMe（长上下文场景）

- [ ] **Train**
  - [ ] Megatron TP=8, PP=4, DP=N
  - [ ] FlashAttention 3
  - [ ] Gradient Checkpointing
  - [ ] BF16 + FP32 master weight

- [ ] **权重同步**
  - [ ] 优先 NCCL over RDMA
  - [ ] FP8 量化传输
  - [ ] 流水线 save/load

- [ ] **Reward**
  - [ ] 可验证奖励优先于 Reward Model
  - [ ] 混合奖励防 hacking
  - [ ] 沙箱跑代码（gVisor / Firecracker）

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

- **DeepSeek-R1**：纯 GRPO + 可验证奖励，证明了 RL 涌现推理能力的可行性。
- **字节 veRL**：HybridEngine 同卡时分复用，工程极致。
- **阿里 Qwen**：GSPO + Agentic RL，长序列与工具使用的代表。
- **Kimi K2**：超长上下文 + 大规模 Agentic RL。
- **NVIDIA NeMo-RL**：NVLink + TensorRT-LLM 全栈优化。
- **共同经验**：Rollout 占大头、可验证奖励优先、KL 惩罚必须、长尾要治理、监控要细。

下一章我们把这些经验提炼为可执行的最佳实践。
