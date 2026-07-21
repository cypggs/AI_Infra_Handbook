# RL Post-Training Mini Demo

用纯 Python 标准库实现的微型 RL Post-Training 系统，演示 GRPO / Rollout-Train 分离 / 权重版本同步等核心机制。

## 快速开始

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m rl_post_training_mini.demo
```

## 六个场景

1. **简单 GRPO 一 step**：完整跑通 Rollout → Reward → Advantage → Update → Sync
2. **多 step 收敛**：观察 reward 曲线、KL 散度、长度变化
3. **Rollout/Train 分离与权重版本**：版本一致性守护
4. **KL 惩罚防爆**：β 系数对策略稳定性的影响
5. **长尾生成与 Continuous Batching**：长短样本混合调度
6. **Reward Hacking 检测**：可验证奖励权重 α 的抗 hack 能力

## 模块

```
rl_post_training_mini/
├── model.py        # TinyPolicy (bigram) + TinyRewardModel
├── algorithms.py   # GRPO / PPO clip / KL
├── rollout.py      # RolloutWorker（模拟 vLLM）
├── reward.py       # RewardService（可验证 + RM 混合）
├── trainer.py      # TrainWorker（PPO 更新）
├── controller.py   # Controller（step 编排）
├── buffer.py       # ExperienceBuffer
└── clock.py        # FakeClock / RealClock
```

## 与真实系统的映射

| Mini Demo | 真实系统 |
|---|---|
| TinyPolicy | 70B Transformer |
| RolloutWorker | vLLM + SGLang |
| RewardService | 可验证奖励 + RM 服务 |
| TrainWorker | Megatron-LM / FSDP |
| Controller | veRL RayPPOTrainer |
