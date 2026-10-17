# 10. 面试题

## 一句话理解

> RL Post-Training 的面试题主要考察三件事：**算法是否理解**（PPO vs GRPO vs DPO）、**工程是否落地**（Rollout/Train 怎么部署）、**问题是否能排查**（reward hacking / KL 爆炸 / 长尾）。

## 一、概念与算法

### Q1：RLHF 和 RLVR 有什么区别？

**A**：

- **RLHF**（RL from Human Feedback）：用人类偏好数据训练 Reward Model，再用 RM 给模型打分。代表：InstructGPT、ChatGPT、Claude。
- **RLVR**（RL with Verifiable Rewards）：用**可自动验证的规则**直接打分（数学答案比对、代码跑测试），不需要 Reward Model。代表：DeepSeek-R1、Qwen3。

**工程差异**：
- RLHF 需要部署 RM 服务，占 GPU；RLVR 只需 CPU 跑脚本。
- RLHF 容易被 hack；RLVR 不会被 hack。
- RLHF 适用主观任务；RLVR 适用客观任务。

### Q2：PPO、GRPO、DPO 的核心区别？

**A**：

| 算法 | Critic | Rollout | 在线/离线 | 适用 |
|---|---|---|---|---|
| **PPO** | 需要 | 需要 | 在线 | 通用 |
| **GRPO** | 不需要 | 需要 | 在线 | 推理训练 |
| **DPO** | 不需要 | 不需要 | 离线 | 快速对齐 |

**GRPO 对 PPO 的关键改进**：用 group 内 mean 作为 baseline，省掉 Critic。

**DPO 的本质**：把 RL 问题转化为监督学习问题，用偏好数据对直接训练。

### Q3：GRPO 的 advantage 是怎么计算的？

**A**：

```python
# 对每个 prompt 生成 G 个 response
rewards = [r1, r2, ..., rG]
mean = sum(rewards) / G
std = sqrt(sum((r - mean)^2 for r in rewards) / G)

# 每个样本的 advantage
advantages = [(r - mean) / (std + eps) for r in rewards]
```

**关键点**：
- 组内归一化，advantage 自然 zero-mean。
- 不需要 Critic 网络，省显存。
- 要求每个 prompt 生成多个 response（G=8-64）。

### Q4：什么是 On-Policy 和 Off-Policy？RL Post-Training 是哪种？

**A**：

- **On-Policy**：训练数据由**当前策略**生成。PPO/GRPO 是 On-Policy。
- **Off-Policy**：训练数据可以来自**旧策略或其他策略**。DQN、SAC 是 Off-Policy。

**RL Post-Training 是 On-Policy**，这意味着：
- 每个 step 都要重新 Rollout。
- 权重必须及时同步到 Rollout 端。
- GPU 利用率挑战大（Rollout 和 Train 不能并行）。

**工程折中**：Near On-Policy（允许滞后 1-N step + ratio clip）。

**2026 年的标准答案**：半异步/全异步 + 三重陈旧性控制——
1. **逐样本版本打标**：样本记录 `weight_version`，超龄丢弃；
2. **深度上界**：缓冲队列限容，限制最大 lag；
3. **TIS 修正**：lag 样本按 `clip(π_new/π_old, 1-ε, 1+ε)` 截断加权。

代表实现：veRL v0.9 V1 trainer（separate_async 还支持训练侧空闲 GPU 借给生成侧）、AReaL 2.0 全异步微服务、OpenRLHF FlashREINFORCE（单样本 + KL 信任域，取消 group 等待）。

## 二、架构与工程

### Q5：RL Post-Training 系统的四大组件是什么？

**A**：

1. **Controller**：编排 step、路由数据、聚合 metric。
2. **Rollout Worker**：用 vLLM/SGLang 生成 response。
3. **Reward Service**：计算 reward（规则 / RM / 混合）。
4. **Train Worker**：用 Megatron/FSDP 执行 PPO 更新。

加上 **Experience Buffer**（数据中转）和 **Weight Store**（权重中转）构成完整系统。

### Q6：Rollout 和 Train 怎么部署？同卡还是分卡？

**A**：

**同卡（Co-located）**：
- 优点：GPU 利用率高、权重零拷贝
- 缺点：引擎切换开销、显存需要精细管理
- 代表：veRL HybridEngine

**分卡（Disaggregated）**：
- 优点：独立优化、独立扩缩、故障隔离
- 缺点：权重同步网络开销大
- 代表：OpenRLHF

**生产实践**：
- 中小规模（<100 卡）→ 同卡
- 大规模（>500 卡）→ 分卡 + NCCL over RDMA

**2026 年的新选项**（veRL v0.9 V1 trainer）：
- **sync**：传统同步循环。
- **colocate_async**：同卡部署，rollout 与 train 时间分片但可重叠。
- **separate_async**：分卡部署，训练侧完成更新后空闲 GPU 借给生成侧——不再设固定 Rollout:Train 配比。

### Q7：Rollout 阶段怎么优化？

**A**：

1. **推理引擎**：vLLM V1（默认）/ SGLang（多轮）/ TensorRT-LLM（NVIDIA 栈）。
2. **Prefix Caching**：GRPO 同一 prompt 的 G 个 sample 共享 KV，省 50% prefill。
3. **Continuous Batching**：长短样本混合，GPU 不空转。
4. **长尾治理**：length-aware batching + early abort + partial rollout。
5. **KV Cache offload**：长上下文场景把 KV 卸载到 CPU/NVMe。

### Q8：权重同步怎么做？

**A**：

**同步方式**：
- NVLink 直传（同节点）
- NCCL over RDMA（跨节点）
- 共享 NVMe（跨集群）
- 对象存储（容灾）

**优化**：
- FP8 量化（带宽减半）
- 增量同步（只传 delta）
- 流水线（layer-by-layer）

**频率**：
- 每 step 同步（On-Policy）
- 每 N step 同步（Near On-Policy）
- 异步（Off-Policy）

### Q9：Agentic RL 给基础设施带来什么新挑战？

**A**：

1. **环境多样性**：终端、浏览器、代码执行器，每个都是分布式系统。
2. **长 Horizon**：单个 episode 上百轮交互（Kimi K3 达数百次工具调用、1M 上下文），Experience Buffer 设计复杂。
3. **异步必须**：环境延迟长，Rollout 必须异步，引入 Off-Policy 偏差。
4. **沙箱安全**：执行模型生成的代码必须隔离（gVisor / Firecracker）。
5. **工具集成**：MCP / function calling / file system 都要打通。
6. **沙箱平台化**（2026 新答案）：环境不再是"脚本"，而是独立平台——DeepSeek DSec 日产约 300 万沙箱、峰值 38 万并发；AgentENV 用 Firecracker microVM 做到小于 50ms 快照恢复、单环境 fork 16 子环境。关键机制是**有状态 rollout 与可抢占训练分离**：环境会话可挂起/恢复，GPU 训练可被回收。

## 三、问题排查

### Q10：训练中 reward 突然飙升后崩溃，可能是什么原因？

**A**：

最可能是 **Reward Hacking**：

- Reward Model 被策略"欺骗"，给出高分但实际质量差。
- 常见手法：堆长度、堆关键词、模式匹配。

**排查**：
1. 抽样人工检查 reward 高的样本。
2. 看 response 长度是否异常增长。
3. 看 KL 是否同步飙升。

**对策**：
1. 混合可验证奖励（α=0.7-0.9）。
2. 加 KL penalty。
3. 加长度约束。
4. 定期人工抽检。

### Q11：KL 散度爆炸（>50）怎么处理？

**A**：

**原因**：
- 学习率过高。
- PPO clip 太松（ε 太大）。
- KL penalty 系数 β 太小。
- Advantage 估计不准。

**对策**：
1. 降低学习率（减半）。
2. 收紧 clip（ε 从 0.2 降到 0.1）。
3. 提高 β（从 0.01 到 0.1）。
4. 减小 batch size（更稳定的估计）。

### Q12：Rollout 吞吐持续下降，可能是什么原因？

**A**：

**排查清单**：
1. **KV Cache 泄露**：vLLM 内部 cache 未释放 → 定期重启实例。
2. **CUDA Graph 失效**：权重更新后 graph 没重建 → 检查 load_weights 逻辑。
3. **长度分布变化**：response 越来越长 → 监控 length 分布。
4. **Prefix Caching 命中率下降**：group 路由是否还正确。
5. **网络/存储瓶颈**：权重同步抢占带宽 → 分开 QoS。

### Q13：训练 loss 出现 NaN，怎么排查？

**A**：

**排查步骤**：
1. 检查 advantage 是否有 NaN/Inf（reward 异常）。
2. 检查 logprob 是否有 -Inf（token 概率为 0）。
3. 检查梯度是否爆炸（grad_norm 监控）。
4. 检查学习率是否过高。

**对策**：
1. 过滤异常 reward（NaN → 0）。
2. logprob clamp 到 [-20, 0]。
3. Gradient clipping（max_norm=1.0）。
4. 降低学习率 + warmup。

### Q14：半异步训练中样本丢弃率飙升，怎么排查？

**A**：

**排查清单**：
1. **生成侧跟不上训练侧**：rollout 吞吐下降（KV 泄露、PD 池配比失衡）→ 平均 lag 顶到上界，超龄样本被批量丢弃。
2. **权重同步变慢**：delta 同步超时、网络争抢 → 训练 step 变短而 rollout 周期没变，相对 lag 放大。
3. **深度上界设太紧**：max_lag 从 2 改到 1，丢弃率立刻上升——先确认是配置变更还是系统退化。
4. **样本长度分布漂移**：response 变长导致 rollout 周期变长。

**对策**：
1. 放宽深度上界或增大 rollout 集群。
2. 超龄样本不直接丢，降级为 TIS 修正样本（权重截断）——用算法换数据。
3. 监控 `rl_sample_mean_lag` 与 `rl_sample_drop_ratio`，告警阈值分别设 2 与 20%。

## 四、设计题

### Q15：设计一个支持 70B 模型、1000 张 H100 的 RL Post-Training 系统

**A**：

**资源划分**：
- 700 卡 Rollout：vLLM，TP=8 × 87 instances + 1 个 LB
- 250 卡 Train：Megatron，TP=8 × PP=4 × DP=7
- 32 卡 Reward Model（如需要）
- 16 卡 Controller + 数据服务

**网络**：
- 节点内 NVLink
- 节点间 800G RDMA
- 独立权重同步网络（NCCL over RDMA）

**存储**：
- 共享 NVMe 集群（PB 级）
- 对象存储作为容灾

**关键设计**：
1. Rollout 用 vLLM V1 + Prefix Caching + Continuous Batching（评估 PD 分离）
2. Train 用 Megatron + FlashAttention 3 + Gradient Checkpointing
3. 权重每 step 同步，delta 分片 + FP8 量化 + NCCL/NIXL 直传
4. 半异步（lag ≤ 2）+ 逐样本版本打标 + TIS 修正，训练侧空闲 GPU 借给生成侧
5. Prometheus + Grafana 全指标监控（含 lag / drop ratio）

### Q16：如何评估一个 RL Post-Training 系统的好坏？

**A**：

**性能指标**：
- Rollout 吞吐（token/s/GPU）
- Train MFU（>35% 为优秀）
- 整体 wall time / step
- GPU 利用率（Rollout >80%, Train >50%）

**稳定性指标**：
- reward 曲线平滑上升
- KL 在 1-10 范围
- length 分布稳定
- ratio clip frac 在 5-20%

**算法指标**：
- 下游任务 eval（AIME / MATH / HumanEval）
- 与 baseline 对比的 win rate

**成本指标**：
- $ / step
- $ / 1% 能力提升

## 本章小结

- **算法**：PPO / GRPO / DPO 区别、GRPO advantage 计算、On-Policy vs Off-Policy 与三重陈旧性控制。
- **工程**：四大组件、同卡 vs 分卡 vs V1 trainer 三模式、Rollout 优化（server-based / PD 分离）、权重同步增量化。
- **排查**：Reward hacking、KL 爆炸、Rollout 吞吐下降、loss NaN、异步样本丢弃率飙升。
- **设计**：1000 卡集群设计、评估指标体系。
