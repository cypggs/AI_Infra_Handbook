# 5. 核心模块

## 一句话理解

> RL Post-Training 系统由五个核心模块构成：**Controller、Rollout Worker、Reward Service、Train Worker、Experience Buffer**。每个模块都有明确的边界与接口，便于独立替换与扩展。

## 模块一：Controller（控制器）

### 职责

Controller 是 RL 系统的"大脑"，负责：

1. **Step 编排**：决定每个 step 的 Rollout/Reward/Train 时序
2. **数据路由**：把 prompts 分给 Rollout Worker，把样本分给 Train Worker
3. **资源调度**：动态调整 worker 数量
4. **版本管理**：跟踪每个样本的 weight_version
5. **Metric 聚合**：收集所有 worker 的指标并汇总

### 关键接口

```python
class Controller:
    def step(self) -> StepMetrics:
        """执行一个完整 RL step"""
        prompts = self.sample_prompts()
        rollouts = self.rollout_worker.generate(prompts)
        rewards = self.reward_service.score(rollouts)
        advantages = self.compute_advantage(rollouts, rewards)
        train_metrics = self.train_worker.update(rollouts, advantages)
        self.sync_weights()
        return StepMetrics(...)

    def sample_prompts(self) -> list[Prompt]:
        """从 dataset 采样一个 batch"""
        
    def compute_advantage(self, rollouts, rewards) -> list[float]:
        """PPO / GRPO advantage 计算"""
```

### 实现要点

- **高可用**：通常用 leader election（K8s Lease / Ray Actor）保证单点。
- **状态持久化**：step 计数、dataset offset、metric 历史需要持久化到 etcd / S3。
- **可观测**：每个 step 的 reward / KL / length / throughput 必须实时上报。

## 模块二：Rollout Worker（生成器）

### 职责

Rollout Worker 用当前 policy 模型生成 response，是系统的"数据生产者"。

### 关键接口

```python
class RolloutWorker:
    def generate(
        self,
        prompts: list[Prompt],
        sampling_params: SamplingParams,
        weight_version: int,
    ) -> list[Rollout]:
        """生成一组 response，返回带 logprobs 的完整轨迹"""
        
    def update_weights(self, weight_path: str, version: int):
        """热加载新权重"""
        
    def health_check(self) -> bool:
        """KV cache / GPU 状态"""
```

### 实现要点

1. **推理引擎**：vLLM / SGLang / TensorRT-LLM。生产环境首选 vLLM V1（V1 引擎默认开启 Prefix Caching 与 Continuous Batching）。
2. **logprobs 返回**：必须开启，PPO 的 ratio 计算需要 π_old(a|s)。
3. **Prefix Caching**：同一 prompt 的 G 个 sample 共享 prompt 的 KV，节省 50% prefill 算力。
4. **Continuous Batching**：让长短样本混合跑，GPU 不空转。
5. **权重热加载**：vLLM 支持 `load_weights` API，无需重启进程。

### 显存模型

一个 70B BF16 模型的 Rollout Worker：

```
模型权重:    70B × 2B = 140 GB（用 TP=8 切到 8 卡，每卡 17.5GB）
KV Cache:    取决于 max_model_len × max_num_seqs
             例: 8k ctx × 64 seqs × 2 (K+V) × 80 layers × 8 kv_heads × 128 dim × 2B
             ≈ 20-40 GB
激活:        几 GB
────────────────────────
单卡总占用: 30-60 GB（TP=8）
```

## 模块三：Reward Service（评分服务）

### 职责

对 Rollout 产出的样本计算 reward。

### 三种形态

#### 1. 规则评分（Verifiable Reward）

```python
class VerifiableReward:
    def score(self, prompt, response) -> float:
        if prompt.task_type == "math":
            return self.math_check(prompt.answer, response)
        elif prompt.task_type == "code":
            return self.run_tests(prompt.test_cases, response)
```

**实现要点**：
- **沙箱**：代码执行必须隔离（参考 [Agent 沙箱](/05-agent/agent-os/)）。
- **超时**：每个样本限 1-5s，防止单个样本阻塞。
- **并行**：用进程池/Ray task 并发跑，吞吐上千样本/秒。

#### 2. Reward Model 服务

```python
class RewardModelService:
    def __init__(self):
        self.engine = vllm.LLM(model="rm-7b", ...)
    
    def score(self, prompt, response) -> float:
        output = self.engine.generate(prompt + response)
        return output.scalar_value
```

**实现要点**：
- 用 vLLM 部署，走 OpenAI-compatible API。
- 独立扩缩容（reward 计算量是 rollout 的 1/G）。

#### 3. 混合评分

```python
final_reward = (
    α * verifiable_reward +
    β * reward_model_score +
    γ * format_reward +
    δ * length_penalty
)
```

## 模块四：Train Worker（训练器）

### 职责

读取 Experience Buffer 中的样本，执行 PPO/GRPO 更新。

### 关键接口

```python
class TrainWorker:
    def update(self, batch: ExperienceBatch) -> TrainMetrics:
        """对一个 batch 做若干 epoch 的 PPO 更新"""
        for epoch in range(self.n_epochs):
            for mini_batch in batch.split(self.mini_batch_size):
                loss = self.ppo_loss(mini_batch)
                loss.backward()
            self.optimizer.step()
        return metrics
        
    def save_checkpoint(self, path: str):
        """保存权重 + optimizer state"""
```

### 实现要点

1. **训练框架**：Megatron-LM / FSDP / DeepSpeed。
2. **并行策略**：TP=8, PP=4, DP=N，与预训练一致。
3. **PPO Loss**：
   ```python
   ratio = exp(logp_new - logp_old)
   surr = min(ratio * adv, clip(ratio, 1-ε, 1+ε) * adv)
   policy_loss = -surr.mean()
   kl = (logp_new - logp_ref).mean()
   loss = policy_loss + β * kl
   ```
4. **Gradient Checkpointing**：长序列必须开启，否则显存爆炸。
5. **FlashAttention**：训练时必须用 FA2/FA3，否则 OOM。

### 显存模型

70B BF16 模型 + AdamW：

```
参数:        70B × 2B = 140 GB
梯度:        70B × 2B = 140 GB
优化器:      70B × 8B (m, v, fp32 master) = 560 GB
激活:        几十 GB（取决于 batch 与序列长度）
─────────────────────
总计: ~840 GB（需要 TP=8 × PP=4 × DP=N 分布式）
```

## 模块五：Experience Buffer（经验缓冲）

### 职责

存储 Rollout 产出的样本，供 Train 消费。

### 两种模式

#### 1. 在线 buffer（On-Policy）

```
Rollout → Buffer → Train (立即消费) → 清空
```

- 容量 = 1 个 step 的 batch
- 样本**只用一次**就丢弃
- 强一致性，PPO/GRPO 标准用法

#### 2. 回放 buffer（Off-Policy / Replay）

```
Rollout → Buffer (容量 N 个 step) → Train (随机采样)
```

- 样本可**重复使用**多次
- 提高样本效率，但引入 off-policy 偏差
- Agentic RL 常用（环境延迟长，样本宝贵）

### 数据结构

```python
@dataclass
class Experience:
    prompt_ids: list[int]
    response_ids: list[int]
    logprobs: list[float]       # π_old 的 logprob
    reward: float
    advantage: float | None     # Train 阶段填充
    weight_version: int
    metadata: dict               # task_type, timestamp, etc.
```

## 模块间通信协议

| 通信对 | 协议 | 序列化 | 特点 |
|---|---|---|---|
| Controller ↔ Rollout | gRPC / Ray Actor | Protobuf / Pickle | 低延迟 |
| Rollout → Reward | HTTP / Ray Task | JSON | 高并发 |
| Controller ↔ Train | Ray Actor / NCCL | PyTorch Tensor | 大 tensor |
| Train → Rollout（权重） | NCCL / 文件 | Safetensors | 大文件 |

## 扩展点

一个好的 RL 框架应该让用户能方便地替换：

| 扩展点 | 默认实现 | 可替换为 |
|---|---|---|
| 推理引擎 | vLLM | SGLang / TensorRT-LLM |
| 训练框架 | Megatron | FSDP / DeepSpeed |
| Reward | 规则脚本 | Reward Model / LLM-as-judge |
| 算法 | PPO / GRPO | DPO / REINFORCE / GSPO |
| 调度器 | 本地 | Ray / K8s Job |
| 权重同步 | NCCL | 共享存储 / 对象存储 |

veRL 通过 `Worker` 抽象 + Ray 实现这些扩展；OpenRLHF 通过 `Actor` 抽象 + DeepSpeed 实现。

## 本章小结

五个核心模块各司其职：

- **Controller**：编排 step、路由数据、聚合 metric。
- **Rollout Worker**：vLLM 生成 + logprobs + Prefix Caching。
- **Reward Service**：规则 / Reward Model / 混合。
- **Train Worker**：Megatron PPO 更新 + 分布式并行。
- **Experience Buffer**：在线（on-policy）或回放（off-policy）。

模块间通过明确的接口解耦，便于独立优化与替换。下一章我们看主流框架如何把这些模块落到具体代码。
