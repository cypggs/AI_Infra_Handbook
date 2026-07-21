# 6. 源码分析

## 一句话理解

> 读懂 veRL 和 OpenRLHF 的源码，就读懂了 2026 年 RL Post-Training 基础设施的两种主流范式：**Ray Actor 编排的显式分离**（OpenRLHF）vs **Hybrid Engine 的灵活部署**（veRL）。

## 框架全景对比

| 框架 | 维护方 | 调度底座 | 推理引擎 | 训练框架 | 代表场景 |
|---|---|---|---|---|---|
| **veRL** | 字节 Seed | Ray + 自研 | vLLM / SGLang | FSDP / Megatron | 生产级 RL |
| **OpenRLHF** | 开源社区 | Ray | vLLM | DeepSpeed | 研究 + 生产 |
| **TRL** | HuggingFace | 单进程 | transformers | transformers / PEFT | 小规模教学 |
| **NeMo-RL** | NVIDIA | Ray | TensorRT-LLM | Megatron | NVIDIA 生态 |
| **AReaL** | 蚂蚁 | 自研 | SGLang | FSDP | 大规模异步 |
| **slime** | 清华 | Ray | SGLang | Megatron | GLM 系列 |
| **ROLL** | 阿里 | Ray | vLLM | Megatron | Qwen Agentic |

下面重点分析 **veRL** 和 **OpenRLHF** 两个最有代表性的框架。

## veRL 源码分析

### 仓库结构

```
verl/
├── workers/                    # 各种 Worker 抽象
│   ├── actor/                  # Policy (Actor) 训练
│   ├── critic/                 # Critic 训练（PPO）
│   ├── rollout/                # Rollout 生成
│   │   ├── vllm_rollout.py     # vLLM 后端
│   │   └── sglang_rollout.py   # SGLang 后端
│   └── reward_model/           # Reward Model
├── trainer/                    # 训练主循环
│   ├── ppo/                    # PPO 算法
│   │   ├── ray_trainer.py      # RayPPOTrainer
│   │   └── core_algos.py       # PPO/GRPO/DPO 算法实现
│   └── fsdp_sft_trainer.py     # SFT
├── single_controller/          # 自研 Ray 调度抽象
│   ├── base/                   # Worker / WorkerGroup 基类
│   └── ray/                    # Ray 后端实现
├── models/                     # 模型封装
│   └── transformers/           # HF transformers 集成
├── utils/                      # 工具
└── protocol.py                 # DataProto 数据协议
```

### 核心抽象：DataProto

veRL 用 `DataProto` 作为模块间的统一数据协议：

```python
# verl/protocol.py
@dataclass
class DataProto:
    batch: TensorDict          # tensor 数据（input_ids, logprobs, rewards）
    non_tensor_batch: dict     # 非 tensor 数据（prompt 文本、metadata）
    meta_info: dict            # 全局信息（weight_version, step）
```

**设计亮点**：
- **TensorDict** 让 batch 内的 tensor 可以按 key 索引，又能整体 to(device)。
- **non_tensor_batch** 保留文本等元数据，避免反复 detokenize。
- 所有 Worker 接口都用 `DataProto` 作为输入输出，**类型统一**。

### 核心抽象：Worker + WorkerGroup

```python
# verl/single_controller/base/worker.py
class Worker:
    def __init__(self, config):
        self.config = config
    
    def init_model(self):
        """子类实现：初始化模型"""
        raise NotImplementedError

# verl/single_controller/base/worker_group.py
class WorkerGroup:
    def __init__(self, worker_cls, n_workers):
        self.workers = [worker_cls.remote() for _ in range(n_workers)]
    
    def execute_all(self, method: str, *args, **kwargs):
        """在所有 worker 上并行执行"""
        return ray.get([getattr(w, method).remote(*args, **kwargs) 
                        for w in self.workers])
```

**设计亮点**：
- 用 Ray Actor 抽象分布式 worker，Controller 只需面向 `WorkerGroup` 编程。
- `execute_all` 一行代码完成分布式调用，屏蔽底层 Ray 细节。

### 核心抽象：HybridEngine（同卡时分复用）

veRL 的招牌特性是 `HybridEngine`——让 vLLM 和 FSDP 跑在同一组 GPU 上：

```python
# verl/workers/rollout/vllm_rollout/vllm_rollout_spmd.py
class vLLMRollout(Worker):
    def init_model(self):
        # 与 Trainer 共用同一份 weight
        self.inference_engine = vllm.LLM(
            model=self.config.model_path,
            tensor_parallel_size=self.config.tensor_parallel_size,
            gpu_memory_utilization=0.5,  # 只用一半显存，另一半留给训练
        )
    
    def update_weights(self, weights: TensorDict):
        """从 Trainer 接收新权重"""
        self.inference_engine.llm_engine.model_executor.driver_worker.load_weights(weights)
```

**关键机制**：

1. **显存分时**：训练时 vLLM 的 KV cache 清空，FSDP 用全部显存；生成时反过来。
2. **权重零拷贝**：Trainer 直接把 GPU 上的 weight tensor 传给 vLLM，无需走存储。
3. **CUDA Graph 重建**：切换模式时 vLLM 会重建 CUDA graph，有几秒开销。

### 算法实现：PPO 与 GRPO

```python
# verl/trainer/ppo/core_algos.py
def compute_grpo_advantage(rewards: torch.Tensor, group_ids: torch.Tensor):
    """GRPO advantage：组内归一化"""
    advantages = torch.zeros_like(rewards)
    for group_id in group_ids.unique():
        mask = group_ids == group_id
        group_rewards = rewards[mask]
        mean = group_rewards.mean()
        std = group_rewards.std()
        advantages[mask] = (group_rewards - mean) / (std + 1e-8)
    return advantages

def compute_policy_loss(
    logprobs_new, logprobs_old, advantages, clip_eps=0.2
):
    """PPO clip loss"""
    ratio = torch.exp(logprobs_new - logprobs_old)
    surr1 = ratio * advantages
    surr2 = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps) * advantages
    return -torch.min(surr1, surr2).mean()
```

### 训练主循环：RayPPOTrainer

```python
# verl/trainer/ppo/ray_trainer.py
class RayPPOTrainer:
    def fit(self):
        for step in range(self.total_steps):
            # 1. 采样 prompt
            prompts = self.train_dataset.sample(self.config.batch_size)
            
            # 2. Rollout 生成（vLLM）
            rollouts = self.rollout_wg.generate_sequences(prompts)
            
            # 3. 计算 reward
            rewards = self.reward_wg.compute_reward(rollouts)
            
            # 4. 计算 advantage
            rollouts.batch["advantages"] = compute_grpo_advantage(
                rewards, rollouts.batch["group_ids"]
            )
            
            # 5. 更新 Actor
            actor_metrics = self.actor_wg.update_policy(rollouts)
            
            # 6. (可选) 更新 Critic
            if self.use_critic:
                critic_metrics = self.critic_wg.update_critic(rollouts)
            
            # 7. 权重同步
            self.sync_weights_to_rollout()
```

## OpenRLHF 源码分析

### 仓库结构

```
openrlhf/
├── models/              # Actor / Critic / RewardModel 封装
├── trainer/
│   ├── ppo_trainer.py   # PPO 主循环
│   ├── dpo_trainer.py
│   └── sft_trainer.py
├── cli/                 # 命令行入口
│   ├── train_ppo.py     # 单机 PPO
│   └── train_ppo_ray.py # Ray 分布式 PPO
└── utils/               # Deepspeed / vLLM 工具
```

### 核心抽象：Actor / Critic / Reward / Reference 四模型

OpenRLHF 把 PPO 的四个模型都用 `Actor` 抽象统一：

```python
# openrlhf/models/actor.py
class Actor(nn.Module):
    def __init__(self, model_name, use_flash_attention=True):
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
    
    def forward(self, input_ids, attention_mask):
        return self.model(input_ids, attention_mask).logits
    
    def generate(self, input_ids, **kwargs):
        return self.model.generate(input_ids, **kwargs)
```

四个模型分别实例化：
- **Actor**：要训练的 policy
- **Critic**：估计 value function
- **Reward Model**：打分
- **Reference Model**：KL 约束的参考

### 分布式架构：Ray + vLLM + DeepSpeed

```python
# openrlhf/cli/train_ppo_ray.py
def train():
    # 1. 启动 vLLM 推理服务（独立 Ray Actor）
    vllm_engines = create_vllm_engines(
        num_engines=args.vllm_num_engines,
        tensor_parallel_size=args.vllm_tensor_parallel_size,
    )
    
    # 2. 启动 Actor / Critic / RM / Ref 训练 Worker
    actor_model = RayActorModel.remote(...)
    critic_model = RayCriticModel.remote(...)
    
    # 3. PPO Trainer 编排
    trainer = PPOTrainer(
        actor_model=actor_model,
        critic_model=critic_model,
        vllm_engines=vllm_engines,
        ...
    )
    trainer.fit()
```

**与 veRL 的差异**：
- OpenRLHF **强分离**：vLLM 和 Train 完全独立 Ray Actor，通过 Ray Collective 同步权重。
- veRL **可分离可同卡**：HybridEngine 让两者可以共存于同一 GPU。

### PPO Trainer 主循环

```python
# openrlhf/trainer/ppo_trainer.py
class PPOTrainer:
    def fit(self):
        for step in range(self.total_steps):
            # 1. 用 vLLM 生成 rollout
            rollouts = self.generate_samples(prompts)
            
            # 2. 计算 reward（Reward Model 前向）
            rewards = self.reward_model(rollouts)
            
            # 3. 计算 KL + advantage
            kl = self.compute_kl(rollouts, self.ref_model)
            advantages = self.compute_gae(rewards, values)
            
            # 4. 更新 Actor / Critic（DeepSpeed）
            self.actor_update(rollouts, advantages)
            self.critic_update(rollouts, rewards)
            
            # 5. 权重同步到 vLLM（Ray Collective）
            self.sync_weights()
```

### 权重同步：Ray Collective

```python
def sync_weights(self):
    """通过 Ray Collective 把 Actor 权重广播到 vLLM 引擎"""
    # 1. Actor rank 0 gather 全部参数
    state_dict = self.actor_model.gather_state_dict()
    
    # 2. 通过 Ray Collective 广播
    ray.util.collective.broadcast(state_dict, src_rank=0)
    
    # 3. vLLM 引擎接收并 reload
    for engine in self.vllm_engines:
        engine.update_weights.remote(state_dict)
```

## 共同设计模式

### 1. 推理与训练分离

两个框架都把推理和训练解耦：

| 维度 | veRL | OpenRLHF |
|---|---|---|
| 耦合方式 | HybridEngine（可同卡） | 强制分离（不同 Ray Actor） |
| 权重同步 | 零拷贝（同卡）/ 文件（异卡） | Ray Collective 广播 |
| 推理引擎 | vLLM / SGLang | vLLM |
| 训练框架 | FSDP / Megatron | DeepSpeed |

### 2. Ray 作为调度底座

两个框架都用 Ray 做分布式调度，理由：

- **Actor 模型**：天然适合表示"长期存活的 worker"。
- **异构资源**：可以给 vLLM worker 分配 GPU，给 Reward worker 分配 CPU。
- **Fault Tolerance**：Ray 的 lineage reconstruction 可以自动恢复失败的 actor。

### 3. 算法与工程解耦

`core_algos.py` 只包含纯函数式的算法实现（PPO/GRPO/DPO），不依赖任何分布式细节。这样：

- 单元测试容易（纯 PyTorch tensor 操作）
- 算法可独立迭代
- 工程优化不影响算法正确性

## 值得深入阅读的文件

### veRL

1. `verl/trainer/ppo/ray_trainer.py` — 训练主循环
2. `verl/trainer/ppo/core_algos.py` — PPO/GRPO 算法实现
3. `verl/workers/rollout/vllm_rollout/vllm_rollout_spmd.py` — vLLM 集成
4. `verl/single_controller/base/worker_group.py` — 分布式抽象

### OpenRLHF

1. `openrlhf/cli/train_ppo_ray.py` — Ray PPO 入口
2. `openrlhf/trainer/ppo_trainer.py` — PPO 主循环
3. `openrlhf/models/actor.py` — Actor 抽象

## 一句话总结

> veRL 代表"极致工程优化"——HybridEngine 同卡时分复用、零拷贝权重、灵活的拓扑选择；OpenRLHF 代表"清晰的分离架构"——四模型独立 Actor、Ray Collective 同步、DeepSpeed 后端。理解这两个框架，就掌握了 RL Post-Training 基建的两大流派。

## 本章小结

- **veRL**：DataProto 统一协议 + HybridEngine 同卡复用 + Ray 调度，工程极致。
- **OpenRLHF**：四模型抽象 + Ray Collective 同步 + DeepSpeed 后端，架构清晰。
- **共同模式**：推理/训练分离 + Ray 调度 + 算法/工程解耦。
- **生态**：TRL 适合教学，NeMo-RL 适合 NVIDIA 栈，AReaL/slime/ROLL 是各家自研的代表。

下一章我们用纯 Python 实现一个迷你的 GRPO + Rollout/Train 分离系统。
