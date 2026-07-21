# 11. 延伸阅读

## 一句话理解

> RL Post-Training 是一个跨学科的领域——强化学习理论、分布式系统、推理引擎、训练框架缺一不可。以下资源按"论文 → 框架 → 系统 → 实践"分类，帮你从原理到落地建立完整认知。

## 一、经典论文

### RLHF 奠基

- **Training language models to follow instructions with human feedback**（OpenAI, 2022）
  - InstructGPT 论文，RLHF 的开山之作。
  - https://arxiv.org/abs/2203.02155

- **Constitutional AI: Harmlessness from AI Feedback**（Anthropic, 2022）
  - RLAIF 的代表作，用 AI 反馈代替人类反馈。
  - https://arxiv.org/abs/2212.08073

### PPO 与算法

- **Proximal Policy Optimization Algorithms**（OpenAI, 2017）
  - PPO 原始论文。
  - https://arxiv.org/abs/1707.06347

- **Direct Preference Optimization**（Stanford, 2023）
  - DPO 原始论文，把 RL 转化为监督学习。
  - https://arxiv.org/abs/2305.18290

### 推理能力训练

- **DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning**（DeepSeek, 2025）
  - 纯 RL 涌现推理能力的代表作，GRPO 的工程实践。
  - https://arxiv.org/abs/2501.12948

- **Qwen3 Technical Report**（Alibaba, 2025）
  - GSPO 算法 + Agentic RL 工程实践。
  - https://arxiv.org/abs/2505.09388

- **Kimi K2: Open Agentic Intelligence**（Moonshot, 2025）
  - 大规模 Agentic RL 的代表。
  - https://arxiv.org/abs/2507.20534

### 推理引擎

- **Efficient Memory Management for Large Language Model Serving with PagedAttention**（vLLM, SOSP 2023）
  - vLLM 的 PagedAttention 论文，RL Rollout 的引擎基础。
  - https://arxiv.org/abs/2309.06180

- **SGLang: Efficient Execution of Structured Language Model Programs**（SGLang, 2024）
  - RadixAttention，多轮 Rollout 的关键优化。
  - https://arxiv.org/abs/2312.07104

## 二、开源框架

### 主力框架

- **veRL**（字节 Seed）
  - 生产级 RL 训练框架，HybridEngine 同卡时分复用。
  - https://github.com/volcengine/verl

- **OpenRLHF**
  - 社区最活跃的 RLHF 框架，Ray + vLLM + DeepSpeed。
  - https://github.com/OpenRLHF/OpenRLHF

- **NeMo-RL**（NVIDIA）
  - NVIDIA 官方 RL 框架，深度整合 TensorRT-LLM。
  - https://github.com/NVIDIA/NeMo-RL

- **TRL**（HuggingFace）
  - 教学与小规模实验首选。
  - https://github.com/huggingface/trl

### 各家自研

- **AReaL**（蚂蚁）
  - 大规模异步 RL 训练。
  - https://github.com/inclusionAI/AReaL

- **slime**（清华 / 智谱）
  - GLM 系列的 RL 训练框架。
  - https://github.com/THUDM/slime

- **ROLL**（阿里）
  - Agentic RL 专用。
  - https://github.com/alibaba/ROLL

### 推理引擎

- **vLLM**
  - https://github.com/vllm-project/vllm

- **SGLang**
  - https://github.com/sgl-project/sglang

- **TensorRT-LLM**
  - https://github.com/NVIDIA/TensorRT-LLM

## 三、关键系统与基础设施

### 沙箱与环境

- **e2b**：Agent 沙箱即服务
  - https://github.com/e2b-dev/e2b

- **Firecracker**：AWS 开源的 microVM
  - https://github.com/firecracker-microvm/firecracker

- **gVisor**：Google 用户态内核
  - https://github.com/google/gvisor

### 调度与编排

- **Ray**：分布式 Python 框架，veRL / OpenRLHF 的底座
  - https://github.com/ray-project/ray

- **Kubernetes**：容器编排底座
  - https://kubernetes.io/

### 训练框架

- **Megatron-LM**：NVIDIA 大规模训练框架
  - https://github.com/NVIDIA/Megatron-LM

- **DeepSpeed**：Microsoft 大规模训练框架
  - https://github.com/microsoft/DeepSpeed

- **PyTorch FSDP**：PyTorch 原生分布式
  - https://pytorch.org/docs/stable/fsdp.html

## 四、博客与技术报告

### OpenAI

- **Learning to Reason with LLMs**（o1 发布博客）
  - https://openai.com/index/learning-to-reason-with-llms/

### DeepSeek

- **DeepSeek-R1 发布博客**
  - https://api-docs.deepseek.com/news/news250120

### Anthropic

- **Claude's Character**（Constitutional AI 应用）
  - https://www.anthropic.com/research/claudes-character

### 字节 Seed

- **Seed-Thinking-v1.5**（RL 训练实践）
  - https://github.com/ByteDance-Seed/Seed-Thinking-v1.5

### 阿里 Qwen

- **Qwen3 技术博客**
  - https://qwenlm.github.io/blog/qwen3/

### 技术博客

- **Chip Huyen: RLHF**
  - https://huyenchip.com/2023/05/02/rlhf.html

- **Lilian Weng: LLM Powered Autonomous Agents**
  - https://lilianweng.github.io/posts/2023-06-23-agent/

- **HuggingFace: RLHF 详解**
  - https://huggingface.co/blog/rlhf

## 五、课程与书籍

- **Deep RL Course**（HuggingFace）
  - https://huggingface.co/learn/deep-rl-course

- **Spinning Up in Deep RL**（OpenAI）
  - https://spinningup.openai.com/

- **Reinforcement Learning: An Introduction**（Sutton & Barto）
  - RL 经典教材，第 2 版。
  - http://incompleteideas.net/book/the-book-2nd.html

## 六、相关主题

本手册中的其他主题与 RL Post-Training 深度相关：

- [大模型从 0 到 1](/01-foundation/llm-from-zero/)：预训练与后训练的全景
- [vLLM 详解](/04-llmops/vllm/)：RL Rollout 的核心引擎
- [SGLang 详解](/04-llmops/sglang/)：多轮 Rollout 的优化引擎
- [Ray 详解](/03-ai-platform/ray/)：RL 分布式调度底座
- [Kubernetes 详解](/02-cloud-native/kubernetes/)：RL 集群调度
- [GPU 在 Kubernetes 上的调度](/02-cloud-native/gpu-scheduling/)：Rollout/Train 混合负载调度
- [Agent Runtime 详解](/05-agent/agent-runtime/)：Agentic RL 的环境侧
- [Agent OS 详解](/05-agent/agent-os/)：Agentic RL 的沙箱底座
- [AI SRE 详解](/07-ai-sre/)：RL 训练的可观测性
- [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/)：RL 效果评估

## 一句话总结

> 从 InstructGPT 到 R1，RL Post-Training 用了三年从"对齐技巧"成长为"能力引擎"。理解它需要论文 + 框架 + 系统三重视角——希望这份清单能帮你在自己的场景中复现并超越这些工作。
