# 7. 工程实践：Mini Demo

> 一句话理解：**`rl_post_training_mini` 用纯 Python 标准库实现一个可运行的 GRPO + Rollout/Train 分离系统**——没有 GPU、没有 vLLM、没有 Megatron，但完整保留了 RL Post-Training 的所有关键语义：On-Policy 生成、组内 advantage、PPO clip、KL 惩罚、权重版本同步。

## 7.1 为什么需要这个 Mini Demo

RL Post-Training 系统横跨"推理引擎 + 训练框架 + 调度器"三个世界，真实环境 GPU 成本高、调试链路长。Mini Demo 把核心机制压缩到一个 CPU 可运行的 Python 包，让你可以：

- 单步跟踪"prompt → rollout → reward → advantage → update → sync"的完整闭环。
- 在小数字上验证 GRPO advantage、PPO clip、KL penalty 的数学正确性。
- 理解 Rollout/Train 分离架构中权重版本一致性的工程细节。
- 作为阅读 veRL / OpenRLHF 源码前的"可运行草图"。

## 7.2 快速开始

```bash
cd docs/04-llmops/rl-post-training/mini-demo
pip install -e ".[dev]"               # 仅依赖 pytest，包本体零依赖
pytest tests/ -v                      # 全部测试通过
python -m rl_post_training_mini.demo  # 跑六个端到端场景
```

## 7.3 六个端到端场景

| 场景 | 演示的核心机制 | 对应真实组件 |
|---|---|---|
| **1. 简单 GRPO 一 step** | On-Policy 生成 + 组内归一化 advantage + PPO clip | veRL / OpenRLHF 主循环 |
| **2. 多 step 收敛** | 在多 step 上观察 reward 上升、KL 受控 | 真实训练曲线 |
| **3. Rollout/Train 分离与权重版本** | Rollout 用 v0 权重、Train 更新到 v1、版本不一致检测 | HybridEngine / 权重同步 |
| **4. KL 惩罚防爆** | 不加 KL 时策略漂移崩溃，加 KL 后稳定 | Reference Model + β 系数 |
| **5. 长尾生成与负载均衡** | 不同长度 rollout 样本混合调度 | vLLM Continuous Batching |
| **6. Reward Hacking 检测** | Reward 模型被打分欺骗时，可验证奖励兜底 | 混合奖励设计 |

## 7.4 运行示例

```text
=== 场景 1：简单 GRPO 一 step ===
Batch: 4 prompts × group_size 4 = 16 samples
Mean reward before: 0.250
Mean reward after:  0.312
KL divergence:      0.012
Ratio clipped frac: 0.18

=== 场景 2：多 step 收敛 ===
Step 1: reward=0.250, kl=0.012, length=12.4
Step 5: reward=0.438, kl=0.087, length=14.1
Step 10: reward=0.625, kl=0.182, length=15.6
✓ Reward 单调上升，KL 在合理范围

=== 场景 3：Rollout/Train 分离与权重版本 ===
Rollout used weight_version=3
Train updated to weight_version=4
Detected stale rollout (v3) → discarded
✓ 版本一致性守护工作正常

=== 场景 4：KL 惩罚防爆 ===
Without KL penalty: reward=0.9 → kl=2.5 (崩溃)
With KL penalty (β=0.1): reward=0.7, kl=0.18 (稳定)
✓ KL 惩罚有效防止策略漂移

=== 场景 5：长尾生成与负载均衡 ===
Generated 32 samples, lengths: min=5, max=48, mean=15.2
Rollout wall time: 1.24s (vs 2.10s without continuous batching)
✓ 长短样本混合，吞吐提升 41%

=== 场景 6：Reward Hacking 检测 ===
Reward Model score: 0.95 (被 hack)
Verifiable reward:  0.00 (真实)
Final mixed reward: 0.19 (α=0.2 权重)
✓ 可验证奖励有效抑制 hacking

✅ 全部 6 个场景通过
```

## 7.5 目录结构与模块对照

```text
rl_post_training_mini/
├── __init__.py             # 导出与真实组件对照表
├── model.py                # TinyPolicy / TinyReward：微型"语言模型"
├── algorithms.py           # GRPO advantage / PPO clip / KL penalty
├── rollout.py              # RolloutWorker：模拟 vLLM 生成 + logprobs
├── reward.py               # RewardService：规则 + Reward Model 混合
├── trainer.py              # TrainWorker：PPO 更新
├── controller.py           # Controller：step 编排 + 权重版本管理
├── buffer.py               # ExperienceBuffer：经验存储
├── clock.py                # FakeClock：精确复现调度时间线
└── demo.py                 # 6 个端到端场景入口

tests/
├── test_algorithms.py      # GRPO/PPO/KL 数学正确性
├── test_rollout.py         # Rollout 与 logprob 一致性
├── test_controller.py      # step 编排与权重版本
├── test_convergence.py     # 多 step 收敛性
└── test_scenarios.py       # 6 个端到端场景
```

## 7.6 与真实系统的映射

| Mini Demo | 真实系统 |
|---|---|
| `TinyPolicy` (bigram 模型) | 70B Transformer (Llama/Qwen) |
| `RolloutWorker` | vLLM + SGLang + Continuous Batching |
| `RewardService` (规则) | 数学比对 / 代码跑测试 |
| `RewardService` (RM) | 独立部署的 Reward Model |
| `TrainWorker` | Megatron-LM / FSDP PPO |
| `Controller` | veRL RayPPOTrainer |
| `weight_version` | HybridEngine 权重同步协议 |
| `FakeClock` | 真实 wall clock + 分布式 trace |

## 7.7 关键代码一瞥

### GRPO advantage 计算（`algorithms.py`）

```python
def compute_grpo_advantage(rewards: list[float], group_ids: list[int]) -> list[float]:
    """组内归一化：(r_i - mean_group) / (std_group + eps)"""
    groups: dict[int, list[int]] = {}
    for idx, gid in enumerate(group_ids):
        groups.setdefault(gid, []).append(idx)
    
    advantages = [0.0] * len(rewards)
    for gid, indices in groups.items():
        group_rewards = [rewards[i] for i in indices]
        mean = sum(group_rewards) / len(group_rewards)
        var = sum((r - mean) ** 2 for r in group_rewards) / len(group_rewards)
        std = var ** 0.5
        for i in indices:
            advantages[i] = (rewards[i] - mean) / (std + 1e-8)
    return advantages
```

### PPO clip loss（`algorithms.py`）

```python
def ppo_clip_loss(
    logprob_new: float,
    logprob_old: float,
    advantage: float,
    clip_eps: float = 0.2,
) -> float:
    """PPO clipped surrogate objective"""
    ratio = math.exp(logprob_new - logprob_old)
    surr1 = ratio * advantage
    surr2 = max(min(ratio, 1 + clip_eps), 1 - clip_eps) * advantage
    return -min(surr1, surr2)
```

### 权重版本守护（`controller.py`）

```python
def step(self):
    prompts = self.sample_prompts()
    current_version = self.weight_version
    
    # Rollout 使用当前权重
    rollouts = self.rollout_worker.generate(
        prompts, weight_version=current_version
    )
    
    # 检查所有 rollout 都用的是同一版本
    for r in rollouts:
        assert r.weight_version == current_version, \
            f"Stale rollout detected: {r.weight_version} != {current_version}"
    
    # ... reward / advantage / train
    
    # Train 完成后版本 +1
    self.weight_version += 1
    self.rollout_worker.update_weights(self.trainer.get_weights(), self.weight_version)
```

## 7.8 运行测试

```bash
$ pytest tests/ -v

tests/test_algorithms.py::test_grpo_advantage_zero_mean PASSED
tests/test_algorithms.py::test_grpo_advantage_group_normalized PASSED
tests/test_algorithms.py::test_ppo_clip_symmetric PASSED
tests/test_algorithms.py::test_kl_penalty PASSED
tests/test_rollout.py::test_logprobs_match_policy PASSED
tests/test_rollout.py::test_continuous_batching PASSED
tests/test_controller.py::test_step_increments_version PASSED
tests/test_controller.py::test_stale_rollout_rejected PASSED
tests/test_convergence.py::test_reward_increases PASSED
tests/test_scenarios.py::test_scenario_1_simple_grpo PASSED
tests/test_scenarios.py::test_scenario_2_multi_step PASSED
tests/test_scenarios.py::test_scenario_3_weight_sync PASSED
tests/test_scenarios.py::test_scenario_4_kl_penalty PASSED
tests/test_scenarios.py::test_scenario_5_long_tail PASSED
tests/test_scenarios.py::test_scenario_6_reward_hacking PASSED

============= 15 passed in 0.42s =============
```

## 7.9 局限与扩展

这个 Mini Demo 故意简化了很多真实复杂度：

- **模型**：用 bigram 概率模型代替 Transformer，但保留了 logprob / sample / update 的接口。
- **并行**：单进程串行，真实系统是万卡分布式。
- **KV Cache**：没有模拟，真实系统这是显存大头。
- **网络**：没有 NCCL / RDMA，真实系统权重同步是网络瓶颈。

可作为下一步扩展：

1. **加 KV Cache 模拟**：让 RolloutWorker 跟踪每个请求的 cache 占用，演示 PagedAttention。
2. **加异步 Rollout**：用线程模拟 Rollout/Train 异步执行，演示 Off-Policy 修正。
3. **加 Reward Model 训练**：让 Reward Model 也是从人类偏好数据学习出来的，演示 RM 训练。
4. **加 Agentic Rollout**：让 Rollout 不只是单轮生成，而是多轮工具调用。

## 本章小结

Mini Demo 用 600 行纯 Python 代码实现了 RL Post-Training 的全部核心机制：

- **算法层**：GRPO advantage / PPO clip / KL penalty
- **架构层**：Rollout/Train 分离 + 权重版本同步
- **工程层**：Continuous Batching / 长尾治理 / Reward Hacking 防御

跑通这个 demo，你就有了阅读 veRL / OpenRLHF 源码的"心智脚手架"。
