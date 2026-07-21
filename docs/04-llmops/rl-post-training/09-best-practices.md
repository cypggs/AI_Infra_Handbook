# 9. 最佳实践

## 一句话理解

> RL Post-Training 的最佳实践可以总结为：**让 Rollout 跑满、让 Train 稳定、让 Reward 可信、让同步不卡**。每一条都对应一组具体的工程动作。

## 一、算法选择

### 1.1 优先 GRPO 而非 PPO

**理由**：
- 去掉 Critic 网络，**显存减半**（70B 模型省 280GB）。
- 算法链路简单，故障点少。
- DeepSeek-R1 已验证其在大规模上的有效性。

**代价**：每个 prompt 需要生成 G=8-64 个 response，**Rollout 压力增大**。

**适用**：
- 数学、代码、推理等有可验证奖励的任务 → **GRPO 必选**
- 通用对话、主观偏好 → **PPO + Reward Model** 更合适

### 1.2 长推理任务的 GSPO 改进

Qwen 团队提出的 **GSPO**（Group Sequence Policy Optimization）：把 token-level importance sampling 改为 sequence-level，解决长序列（>4k token）训练时的不稳定。

**实践经验**：当平均 response 长度超过 2k token 时，考虑用 GSPO 替代 GRPO。

### 1.3 DPO 的适用边界

DPO（Direct Preference Optimization）不需要 Rollout，直接用偏好数据对训练：

- **优点**：工程极简，无推理引擎。
- **缺点**：是 Off-Policy 算法，能力上限低于 RL。

**适用**：快速对齐、资源受限、主观偏好任务。**不适用**：推理能力训练。

## 二、Rollout 优化

### 2.1 推理引擎选择

| 引擎 | 优势 | 适用 |
|---|---|---|
| **vLLM V1** | 生态最大、功能最全 | 默认选择 |
| **SGLang** | RadixAttention 多轮共享 KV | Agentic RL、多轮对话 |
| **TensorRT-LLM** | NVIDIA 硬件极致性能 | NVIDIA 全栈用户 |

### 2.2 关键配置

```python
# vLLM 推荐配置（Rollout）
vllm.LLM(
    model=model_path,
    tensor_parallel_size=8,
    gpu_memory_utilization=0.85,           # 充分利用显存
    max_model_len=32768,                   # 按任务调整
    enable_prefix_caching=True,            # 必须开启（GRPO group 共享）
    enable_chunked_prefill=True,           # 长 prompt 必须
    max_num_seqs=256,                      # 提高并发
    swap_space=4,                          # KV cache offload
)
```

### 2.3 Sampling 参数

| 参数 | RLVR 推荐 | RLHF 推荐 | 说明 |
|---|---|---|---|
| temperature | 1.0 | 0.7-1.0 | 探索需要高温 |
| top_p | 1.0 | 0.9-1.0 | 不截断 |
| top_k | -1 | -1 | 不限制 |
| max_tokens | 任务上限 | 1024-4096 | 防失控 |

### 2.4 长尾治理

- **Continuous Batching**：默认开启。
- **Length-aware batching**：按 prompt 预估长度分桶。
- **Early abort**：超过 max_tokens 的样本截断并给 0 reward。
- **Partial Rollout**：达到 80% 完成度就进入 Train。

## 三、Train 优化

### 3.1 并行策略

70B 模型的典型并行配置：

```
TP=8 (intra-node NVLink)
PP=4 (inter-node)
DP=N (scale out)
```

**经验**：
- TP 尽量在单机内（NVLink 高带宽）。
- PP 跨节点，尽量减少（气泡时间）。
- DP 是主要扩展维度。

### 3.2 显存优化

- **FlashAttention 3**：必须用，省 50% 激活显存。
- **Gradient Checkpointing**：长序列必须开，重计算换显存。
- **ZeRO-3**（FSDP/DeepSpeed）：参数+梯度+优化器全部切分。
- **BF16 + FP32 master**：混合精度标准配置。

### 3.3 稳定性

- **Gradient Clipping**：`max_norm=1.0`。
- **KL penalty**：`β=0.01-0.1`，监控 KL 在 1-10 范围。
- **Ratio clip**：`ε=0.2`，监控 clip fraction 在 5-20%。
- **学习率 warmup**：前 100 step 线性 warmup。

## 四、Reward 设计

### 4.1 奖励优先级

```
可验证奖励 > 规则奖励 > Reward Model > LLM-as-judge
```

### 4.2 防 Reward Hacking

**症状**：reward 突然飙升，但人工抽检发现质量没提升。

**对策**：
1. **混合奖励**：`final = α * verifiable + (1-α) * reward_model`，α=0.7-0.9。
2. **KL penalty**：防止策略偏离 reference 太远。
3. **长度约束**：防止靠堆长度骗 reward。
4. **定期人工抽检**：每 N step 抽样检查。

### 4.3 代码任务的沙箱

代码执行必须用沙箱：

- **gVisor**：用户态内核，性能好。
- **Firecracker**：microVM，隔离强。
- **Kata Containers**：容器 + VM 混合。

**配置**：
- 网络隔离（无出网）
- 文件系统隔离（只读 root + tmpfs）
- 资源限制（CPU=1, MEM=2GB, timeout=5s）

## 五、权重同步

### 5.1 同步频率

- **每 step 同步**（On-Policy）：算法收敛最强，网络压力最大。
- **每 N step 同步**（Near On-Policy）：N=2-8，配合 ratio clip。
- **异步同步**（Off-Policy）：算法收敛弱，GPU 利用率最高。

**推荐**：从每 step 同步开始，出现网络瓶颈再放宽。

### 5.2 同步通道

| 通道 | 延迟 | 适用 |
|---|---|---|
| NVLink 直传 | <1s | 同节点 |
| NCCL over RDMA | 1-10s | 跨节点 |
| 共享 NVMe | 10-30s | 跨集群 |
| 对象存储 | 分钟级 | 异地容灾 |

### 5.3 传输优化

- **FP8 量化**：带宽减半，精度损失 <1%。
- **增量同步**：只传 delta weight。
- **流水线**：layer-by-layer 流式传输。

## 六、可观测性

### 6.1 必看指标

```yaml
# Prometheus 指标
rl_step_total                    # 总 step 数
rl_reward_mean                   # 平均 reward
rl_reward_std                    # reward 方差
rl_kl_divergence                 # KL 散度
rl_response_length_mean          # 平均 response 长度
rl_ratio_clip_frac               # PPO clip 比例
rl_rollout_throughput_tps        # Rollout token/s
rl_train_mfu                     # 训练 MFU
rl_weight_sync_duration_seconds  # 权重同步耗时
rl_rollout_worker_utilization    # Rollout GPU 利用率
rl_train_worker_utilization      # Train GPU 利用率
```

### 6.2 告警规则

```yaml
- alert: RLRewardCollapse
  expr: rate(rl_reward_mean[10m]) < -0.1
  for: 5m

- alert: RLKLExplosion
  expr: rl_kl_divergence > 50
  for: 1m

- alert: RLLengthCollapse
  expr: rate(rl_response_length_mean[10m]) < -0.3
  for: 5m

- alert: RLLowTrainMFU
  expr: rl_train_mfu < 0.2
  for: 15m
```

## 七、常见踩坑

### 7.1 训练崩溃

**症状**：loss NaN 或 reward 骤降。

**排查**：
1. 学习率是否过高？
2. KL 是否失控？
3. ratio clip 比例是否 >50%？
4. 是否有 reward 异常值（NaN / Inf）？

**对策**：降低 LR / 提高 KL β / 收紧 clip / 过滤异常 reward。

### 7.2 Rollout 吞吐下降

**症状**：token/s 持续下降。

**排查**：
1. KV cache 泄露？
2. CUDA graph 失效？
3. 长度分布变化？

**对策**：定期重启 vLLM 实例 / 调整 max_num_seqs / 长度分桶。

### 7.3 权重同步超时

**症状**：同步耗时超过 step 时间。

**排查**：
1. 网络带宽是否够？
2. 是否跨 AZ？
3. 是否有其他流量竞争？

**对策**：FP8 量化 / 增量同步 / 拓扑优化 / 专用 RDMA 网络。

## 八、成本优化

### 8.1 Spot 实例

- **Rollout**：可以用 spot（无状态）。
- **Train**：必须 reserved（有状态 + Gang）。
- **Reward**：可以 spot。

### 8.2 弹性伸缩

- 根据当前队列深度动态调整 Rollout worker 数量。
- 夜间低峰缩减 Rollout，保留 Train。

### 8.3 异构硬件

- Rollout 用 L40S / H20（推理性价比高）。
- Train 用 H100 / H200 / B200（训练性能优先）。

## 一句话总结

> 把 Rollout 当推理服务优化（vLLM 全套手段），把 Train 当预训练优化（Megatron 全套手段），把 Reward 当产品优化（防 hack、可信），把同步当网络优化（NCCL + 量化 + 流水线）。四个方面都做到位，RL Post-Training 就能稳定产出。

## 本章小结

- **算法**：默认 GRPO，长序列用 GSPO，主观偏好用 PPO。
- **Rollout**：vLLM + Prefix Caching + Continuous Batching + 长尾治理。
- **Train**：TP=8/PP=4/DP=N + FlashAttention + KL penalty。
- **Reward**：可验证优先 + 混合防 hack + 沙箱跑代码。
- **同步**：每 step 优先，FP8 + 增量 + 流水线优化。
- **可观测**：reward / KL / length / clip_frac / MFU 五大指标。
- **成本**：Rollout 用 spot + 异构硬件 + 弹性伸缩。
