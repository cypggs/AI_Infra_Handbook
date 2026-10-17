# 6. 源码分析

## 一句话理解

> 读懂 veRL 和 OpenRLHF 的源码，就读懂了 2026 年 RL Post-Training 基础设施的两种主流范式：**Ray Actor 编排的显式分离**（OpenRLHF）vs **Hybrid Engine 的灵活部署**（veRL）。

## 框架全景对比（截至 2026-10）

| 框架 | 维护方 | 调度底座 | 推理引擎 | 训练框架 | 代表场景 |
|---|---|---|---|---|---|
| **veRL**（v0.9.1，2026-09） | 字节 Seed | Ray + 自研 | vLLM ≥0.18 / SGLang / TRT-LLM | Megatron-Bridge / FSDP / VeOmni / TorchTitan | 生产级 RL + On-Policy Distillation |
| **OpenRLHF**（0.10.x） | 开源社区 | Ray | vLLM | DeepSpeed / Molt | 研究 + 生产，Agentic/VLM |
| **TRL** | HuggingFace | 单进程 | transformers | transformers / PEFT | 小规模教学；异步版设计已定稿 |
| **NeMo-RL** | NVIDIA | Ray | TensorRT-LLM | Megatron | NVIDIA 生态 |
| **AReaL 2.0**（2026-07） | 蚂蚁 + 清华 | 微服务（无 Ray 依赖） | SGLang / vLLM | FSDP | 大规模全异步、Agentic |
| **slime**（v0.4.x） | 清华 / 智谱 | Ray | SGLang | Megatron Core | GLM-5 系列，训练/服务解耦 |
| **ROLL** | 阿里 | Ray | vLLM | Megatron | Qwen Agentic |

2026 年的三条演进主线：**server-based rollout 取代 SPMD rollout**（veRL v0.7 移除 SPMD 模式）、**训练/推理/Agent 微服务化解耦**（AReaL 2.0、slime 生命周期解耦）、**权重同步增量化**（veRL `delta_sharded`、MoE 无损同步）。下面重点分析 **veRL** 和 **OpenRLHF** 两个最有代表性的框架。

## veRL 源码分析

### 版本演进脉络（2026）

- **v0.7（2026-01）**：移除 SPMD rollout，默认 server-based rollout；引入 `AgentLoop` 抽象（`SingleTurnAgentLoop` / `ToolAgentLoop`，可扩展 SWEAgentLoop 等）；支持 vLLM 0.12.0 / SGLang 0.5.6 与 blockwise FP8 rollout；新增 CISPO / SAPO 算法。
- **v0.8.0（2026-06）**：同步 trainer 引入 TransferQueue（128 卡多模态训练最高 2 倍提速）；端到端 On-Policy Distillation（FSDP / Megatron / VeOmni）；SGLang LoRA 与 PD 分离；TRT-LLM async RL。
- **v0.9.0（2026-08-14）**：**V1 PPO trainer 成为默认**（sync / colocate_async / separate_async 三模式）；DeepSeek-V4 GRPO 端到端（Megatron-Bridge + FP8/MXFP4 权重传输）；vLLM PD-disaggregated rollout；vLLM rollout 全确定性；`delta_sharded` checkpoint engine（72B 实测 3.1 倍）；**破坏性变更：不再支持 vLLM < 0.18**。
- **v0.9.1（2026-09-20）**：unified V1 trainer——separate_async 可把训练侧空闲 GPU 借给生成侧；Liger Kernel 集成（actor 更新快 13.5%）；`RequestLoadBalancer` 可插拔 vLLM 路由；TorchTitan 后端权重同步快 10.3 倍（Qwen3-8B / 32 卡）；旧 `fully_async_policy` / `one_step_off_policy` 废弃。

### 仓库结构（v0.9 视角）

```
verl/
├── workers/                    # 各种 Worker 抽象（基于统一 model engine）
│   ├── actor/                  # Policy (Actor) 训练
│   ├── critic/                 # Critic 训练（PPO）
│   ├── rollout/                # Rollout 生成
│   │   ├── vllm_rollout/       # vLLM 后端（server-based）
│   │   └── sglang_rollout/     # SGLang 后端（含 PD 分离）
│   └── reward_model/           # Reward Model
├── trainer/                    # 训练主循环
│   ├── ppo/                    # PPO 算法
│   │   ├── ray_trainer.py      # RayPPOTrainer（V0，逐步被 V1 取代）
│   │   ├── core_algos.py       # PPO/GRPO/GSPO/DAPO/CISPO/SAPO 算法实现
│   │   └── metric.py
│   └── vllm_/fsdp_/megatron_…  # 各引擎的 V1 trainer 实现
├── engine/                     # 统一模型引擎抽象（V1 新增）
├── checkpoint_engine/          # delta_sharded / NCCL / NIXL 权重同步
├── single_controller/          # 自研 Ray 调度抽象
│   ├── base/                   # Worker / WorkerGroup 基类
│   └── ray/                    # Ray 后端实现
├── protocol.py                 # DataProto 数据协议
└── utils/
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

### 核心抽象：AgentLoop（v0.7 新增）

Agentic RL 的关键抽象从"rollout 函数"变成"agent 循环"：

```python
# verl/agent_loop/ 下的伪代码
class AgentLoop:
    async def run(self, sample) -> MultiTurnOutput:
        """定义"一轮任务"的交互逻辑：模型生成 → 工具调用 → 环境反馈 → 续生成"""
        messages = sample.prompt
        while not self.is_done(messages):
            action = await self.rollout(messages)        # vLLM/SGLang 生成
            observation = await self.execute_tool(action) # 沙箱/工具/MCP
            messages = append(messages, action, observation)
        return self.build_output(messages)
```

veRL 内置 `SingleTurnAgentLoop` 与 `ToolAgentLoop`（ReAct 风格工具调用），并允许用户自定义（如 SWEAgentLoop）。这把"环境交互"从框架内部彻底开放为扩展点——配合 server-based rollout，Agentic 请求可以像普通在线服务一样动态 batching。

### 核心抽象：V1 Trainer 与异步模式（v0.9）

```python
# 伪代码：V1 trainer 的三种模式
trainer = V1PPOTrainer(mode="separate_async")  # sync / colocate_async / separate_async
# - sync:        同步循环（原 V0 语义）
# - colocate_async: 同卡部署，rollout 与 train 时间分片但可重叠
# - separate_async: 分卡部署，训练侧完成更新后空闲 GPU 可借给生成侧
```

V1 trainer 的关键设计：rollout 样本带 `weight_version` 进入 TransferQueue，训练侧按陈旧度上界取数并做 TIS 修正；权重通过 checkpoint engine 的 delta 分片直投 vLLM。

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

### 版本演进（2026）

- **v0.8（2025-05）**：引入异步训练 `--async_train` 与异步 Agentic RL `--agent_func_path`（class-based Agent API），rollout / actor / reward 引擎经消息传递独立运行。
- **0.10.x（2026-04 ~ 06）**：端到端 VLM RLHF 与多轮 VLM Agentic RL（图像输入 + 环境截图反馈，`vlm_multiturn_agent.py`）；0.10.4 发布于 2026-06-08。
- **2026-02**：ProRL V2 实践——用 REINFORCE++-baseline 做"延长版" RL（1.5B 推理模型长时间训练不崩）。
- **2026-09**：**FlashREINFORCE**——critic-free、单 rollout 的异步 Agentic RL：不做 group 等待，把二元 KL 信任域直接建立在 vLLM 返回的 logprobs 上（`--algo.advantage.estimator flash_reinforce`）。
- **Molt 后端**：定位为"比 DeepSpeed 更强"的训练后端，面向数千亿参数 RL 训练，工作流与现有一致。

### 仓库结构

```
openrlhf/
├── models/              # Actor / Critic / RewardModel 封装
├── trainer/
│   ├── ppo_trainer.py   # PPO 主循环（含 async 模式）
│   ├── dpo_trainer.py
│   └── sft_trainer.py
├── cli/                 # 命令行入口
│   ├── train_ppo.py     # 单机 PPO
│   └── train_ppo_ray.py # Ray 分布式 PPO
├── agents/              # Agentic RL：可插拔 agent 定义（--agent_func_path）
└── utils/               # Deepspeed / vLLM / Molt 工具
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

## AReaL 2.0：微服务化全异步范式（2026-07）

如果说 veRL / OpenRLHF 代表"Ray Actor 编排的单体框架"，AReaL 2.0（蚂蚁 + 清华，2026-07-01 发布）代表了另一种范式：**用微服务边界替代框架内部抽象**。

### 架构

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────────┐
│   Agent    │   │ Inference  │   │  Training  │   │ Weight Update  │
│  Service   │──→│  Service   │──→│  Service   │←──│    Service     │
│ (环境/沙箱) │   │(SGLang/vLLM)│   │  (FSDP)    │   │ (增量权重广播)  │
└────────────┘   └────────────┘   └────────────┘   └────────────────┘
      四个服务独立部署、独立扩缩容，通过队列/流式协议交换数据
```

- **v1.0（2026-03）** 的招牌是 Proxy Worker：Agent 侧只要改 API endpoint 就能接入 RL 训练，报告相对同步系统提速 2.77 倍。
- **2.0（2026-07）** 把训练、推理、Agent、权重更新拆成四个微服务，内置 Hermes 在线 RL loop 与端到端 SWE（软件工程）RL 训练示例。
- 配套算法改进：KPop / IcePop（2026-06）——基于双向二元 KL 与 importance ratio 的 token 掩码技术，缓解异步带来的偏差。
- 2026-01 起支持华为昇腾 NPU。

### 与前两种范式的对比

| 维度 | veRL / OpenRLHF | AReaL 2.0 |
|---|---|---|
| 组织方式 | Ray Actor 单体框架 | 微服务（可跨集群） |
| 故障域 | 框架内恢复 | 服务级独立重启，rollout 状态外置 |
| 扩展点 | 类继承 / Worker 抽象 | 服务边界（换服务即可） |
| 适合 | 单一训练集群 | 多集群、Agentic 环境分散部署 |

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

1. `verl/trainer/ppo/ray_trainer.py` — V0 训练主循环（理解 baseline）
2. `verl/trainer/ppo/core_algos.py` — PPO/GRPO/GSPO/DAPO/CISPO/SAPO 算法实现
3. `verl/agent_loop/` — AgentLoop 抽象（Agentic RL 扩展点）
4. `verl/checkpoint_engine/` — delta_sharded / NCCL / NIXL 权重同步
5. `verl/workers/rollout/` — vLLM / SGLang server-based rollout 集成

### OpenRLHF

1. `openrlhf/cli/train_ppo_ray.py` — Ray PPO 入口
2. `openrlhf/trainer/ppo_trainer.py` — PPO 主循环（含 async 模式）
3. `openrlhf/agents/` — Agentic RL 可插拔 agent

### AReaL

1. 四微服务拆分与 Hermes loop 的 README 架构图
2. KPop / IcePop token 掩码实现

## 一句话总结

> veRL 代表"极致工程优化"——HybridEngine、server-based rollout、V1 trainer 三模式异步、delta 权重直投；OpenRLHF 代表"清晰的分离架构 + 算法广度"——四模型 Actor、Ray Collective 同步、FlashREINFORCE 单样本异步；AReaL 2.0 代表"微服务化"——用服务边界替代框架抽象。理解这三个框架，就掌握了 RL Post-Training 基建的三大流派。

## 本章小结

- **veRL**：DataProto 统一协议 + HybridEngine + V1 trainer（sync/colocate_async/separate_async）+ checkpoint engine 增量化同步，v0.9 起全面转向 server-based rollout。
- **OpenRLHF**：四模型抽象 + Ray Collective 同步 + DeepSpeed/Molt 后端，算法覆盖 PPO/DAPO/REINFORCE++/FlashREINFORCE，Agentic/VLM 支持最灵活。
- **AReaL 2.0**：训练/推理/Agent/权重更新四微服务全异步，Proxy Worker 一键接入，Agentic RL 的另一种工程答案。
- **共同模式**：推理/训练分离 + 异步流水 + 版本打标陈旧性控制 + 算法/工程解耦。
- **生态**：TRL 适合教学（异步版设计已定稿），NeMo-RL 适合 NVIDIA 栈，slime 以 Megatron/SGLang 生命周期解耦服务 GLM-5。

下一章我们用纯 Python 实现一个迷你的 GRPO + Rollout/Train 分离系统。
