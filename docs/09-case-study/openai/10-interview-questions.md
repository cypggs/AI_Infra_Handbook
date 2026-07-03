# 面试题

以下问题覆盖 OpenAI 基础设施的概念、架构、实现与生产落地。

## 初级

### 1. OpenAI 的训练基础设施主要依赖哪些硬件与网络？

**答案要点**：NVIDIA A100/H100/H200 GPU、NVSwitch/NVLink、NVIDIA Quantum-2 InfiniBand、高吞吐存储、液冷数据中心。

### 2. 什么是 Continuous Batching？为什么对推理很重要？

**答案要点**：动态将不同请求的生成步骤组 batch，提高 GPU 利用率，降低平均延迟。传统 static batching 必须等所有请求完成才能释放资源。

### 3. OpenAI API 为什么要做模型版本管理？

**答案要点**：模型行为可能随版本变化，显式版本让用户可控；支持灰度、A/B 测试与回滚。

### 4. 什么是 KV Cache？为什么需要管理它？

**答案要点**：存储已生成 token 的 key/value，避免重复计算。管理不当会导致内存碎片、上下文长度受限、GPU OOM。

### 5. OpenAI 的 Preparedness Framework 评估哪四类风险？

**答案要点**：Cybersecurity、CBRN（化学/生物/放射/核）、Persuasion、Model Autonomy。

## 中级

### 6. 为什么训练 GPT-4 级别模型时 checkpoint 频率要高？

**答案要点**：数万 GPU 集群故障率高，高频 checkpoint 可将故障损失控制在数分钟到十几分钟；TB 级 checkpoint 写入吞吐也是关键优化点。

### 7. OpenAI 如何降低推理延迟？列出至少三种方法。

**答案要点**：continuous batching、KV cache / prefix caching、speculative decoding、predicted outputs、减少输出 token、streaming、小模型路由。

### 8. OpenAI 与 Microsoft Azure 的合作模式对基础设施有什么影响？

**答案要点**：Microsoft 为 OpenAI co-design 专用超级计算机；从 InfiniBand 网络、存储、调度到故障恢复都针对大模型优化；Azure OpenAI Service 复用同一能力。

### 9. RLHF 在大模型生产中的定位是什么？

**答案要点**：RLHF 是对齐训练的核心方法之一，让模型输出符合人类偏好与安全策略；是持续迭代过程，不是一次性训练。

### 10. 设计一个多租户 LLM API 的限流系统，你会考虑哪些维度？

**答案要点**：按 API key / organization / project、按模型、按并发请求数、按 token per minute、按 tier、按区域容量、支持 burst 与平滑限流。

## 高级

### 11. 如果让你设计一个支持 o1/o3 reasoning 模型的推理平台，与 GPT-4 相比有哪些新挑战？

**答案要点**：测试时计算导致单次请求消耗更多 token 和时间；需要新的成本模型与定价；调度要考虑长链思考任务的资源占用；延迟 SLO 更难满足；需要支持中间 reasoning 的存储与审计。

### 12. OpenAI 如何平衡模型能力释放与安全风险？

**答案要点**：迭代部署、staged release、RLHF/Constitutional AI 对齐、Preparedness Framework 风险评估、Red Teaming、System Cards、部署门槛（high/critical 风险需额外缓解）、滥用监控与快速回滚。

### 13. 数万台 GPU 的训练集群中，网络拓扑如何影响并行策略？

**答案要点**：机架内 NVLink/NVSwitch 带宽最高；机架间/跨 pod InfiniBand 带宽较低、延迟更高。张量并行应尽量放在节点内；数据并行/流水线并行跨节点；MoE all-to-all 需要避免跨 pod 成为瓶颈。

### 14. 如果你要复刻一个最小可用的 OpenAI-compatible API，核心模块有哪些？

**答案要点**：认证授权、限流配额、模型路由、请求解析、推理引擎（模型加载 + continuous batching + KV cache）、输出格式化、安全过滤、流式响应、可观测与计费。

### 15. 从 OpenAI 的 outages 中，你认为最重要的三个教训是什么？

**答案要点**：
- 容量规划必须留足余量并具备快速降级能力。
- 多区域部署与全局状态一致性是可用性关键。
- 新模型/配置必须支持分钟级回滚。

## 小结

OpenAI 案例面试不仅考察知识点，更考察**在规模、成本、延迟、安全之间做 trade-off 的能力**。准备时建议结合具体数字（如 H100 数量、InfiniBand 带宽、latency 优化原则）与真实 outage 场景来回答。
