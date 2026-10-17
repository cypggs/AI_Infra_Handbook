# 阅读指南

欢迎来到 AI Infra Handbook。这是一本面向 AI Infrastructure 工程师的工程手册，目标是系统性地覆盖 AI 基础设施的各个领域。

## 这本手册适合谁？

- AI Infra Engineer / AI Platform Engineer
- LLMOps Engineer / AI SRE
- Platform Engineer / Staff Engineer
- 希望从 Kubernetes / Linux 基础成长到 AI 基础设施设计的架构师

## 阅读建议

### 1. 按学习路线系统阅读

如果你是刚开始系统学习 AI 基础设施，建议先阅读 [学习路线](/10-roadmap/learning-path)，按照从基础到上层、从原理到工程的顺序推进。

### 2. 按主题查阅

如果你已经工作一段时间，可以直接跳到感兴趣的主题：

- 想从大模型训练与推理的全链路开始：[大模型从 0 到 1](/01-foundation/llm-from-zero/)（已上线）
- 想理解 GPU 硬件架构与 CUDA 编程模型：[GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/)（已上线）
- 想理解 Linux 操作系统与性能调优：[Linux 系统与性能调优](/01-foundation/linux-systems/)（已上线）
- 想理解计算机网络与 AI 集群通信底座：[计算机网络](/01-foundation/computer-networks/)（已上线）
- 想理解存储系统与 AI checkpoint/模型加载底座：[存储系统](/01-foundation/storage-systems/)（已上线）
- 想理解分布式系统基础与 AI 集群协调、一致性、容错：[分布式系统基础](/01-foundation/distributed-systems/)（已上线）
- 想了解 LLM 推理引擎：从 [vLLM](/04-llmops/vllm/)、[SGLang](/04-llmops/sglang/)、[TensorRT-LLM](/04-llmops/tensorrt-llm/)、[Triton Inference Server](/04-llmops/triton/) 或 [LLM Gateway](/04-llmops/llm-gateway/) 开始
- 想了解 RL Post-Training（GRPO/PPO、Rollout/Train 分离、veRL/OpenRLHF）：[RL Post-Training 基础设施](/04-llmops/rl-post-training/)（已上线）
- 想了解 AI 编译器与 Kernel 生成（torch.compile/Inductor、Triton 语言、cuTile/CUTLASS、TileLang、Mirage）：[AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/)（已上线）
- 想了解容器编排底座：[Kubernetes](/02-cloud-native/kubernetes/)（已上线）
- 想了解 K8s 之下的执行层（镜像、namespace/cgroup、containerd/runc、OCI）：[容器运行时](/02-cloud-native/container-runtime/)（已上线）
- 想了解 K8s 包管理与部署（Chart、values、三方合并、GitOps）：[Helm](/02-cloud-native/helm/)（已上线）
- 想了解如何把领域运维知识编码成自愈控制循环（CRD、Reconcile、finalizer、KubeRay/Training Operator）：[Operator 模式](/02-cloud-native/operator/)（已上线）
- 想了解 Kubernetes 网络与存储插件接口、生命周期与生产排障（CNI、CSI、NetworkPolicy、VolumeAttachment）：[CNI / CSI 深度](/02-cloud-native/cni-csi/)（已上线）
- 想了解 NVIDIA GPU 在 Kubernetes 上的发现、调度、共享、拓扑感知与治理：[GPU 在 Kubernetes 上的调度](/02-cloud-native/gpu-scheduling/)（已上线）
- 想了解统一分布式 AI 平台：[Ray](/03-ai-platform/ray/)（已上线）
- 想了解 Kubernetes 模型服务平台（InferenceService / ServingRuntime / 金丝雀 / 自动扩缩）：[KServe](/03-ai-platform/kserve/)（已上线）
- 想了解 Kubernetes 上的 ML 平台（Notebook / Pipelines / Katib / Training Operator）：[Kubeflow](/03-ai-platform/kubeflow/)（已上线）
- 想了解开源 ML 生命周期平台（实验追踪 / 模型注册 / 模型治理）：[MLflow](/03-ai-platform/mlflow/)（已上线）
- 想了解 Ray 在 Kubernetes 上的官方 Operator（RayCluster / RayJob / RayService）：[KubeRay](/03-ai-platform/kuberay/)（已上线）
- 想了解工作流编排平台（DAG / Operator / Scheduler / Executor / Metadata DB）：[Airflow](/03-ai-platform/airflow/)（已上线）
- 想了解 Agent Runtime：[Agent Runtime](/05-agent/agent-runtime/)（已上线）
- 想了解 Agent Memory：[Memory](/05-agent/memory/)（已上线）
- 想了解 Multi-Agent：[Multi-Agent](/05-agent/multi-agent/)（已上线）
- 想了解 Agent Reflection：[Reflection](/05-agent/reflection/)（已上线）
- 想了解 Agent 协议：[MCP](/05-agent/mcp/)（已上线）
- 想了解 Agent Planning：[Planning](/05-agent/planning/)（已上线）
- 想了解 Agent Tool Use：[Tool Use](/05-agent/tool-use/)（已上线）
- 想了解 Agent OS：[Agent OS](/05-agent/agent-os/)（已上线）
- 想了解 Personal AI Agent：[Personal AI Agent](/05-agent/personal-agent/)（已上线）
- 想了解 RAG：[RAG](/06-rag/)（已上线）
- 想了解向量数据库与 Embedding 基础设施（HNSW/DiskANN、Milvus/Qdrant/pgvector、Embedding 服务）：[向量数据库与 Embedding 基础设施](/06-rag/vector-db/)（已上线）
- 想了解特征平台与训练数据基础设施（特征偏斜、point-in-time 正确性、Feast/Tecton）：[特征平台与训练数据基础设施](/03-ai-platform/feature-store/)（已上线）
- 想了解 LLM 推理缓存与 KV Cache 管理（PD 分离、Mooncake/LMCache、prefix 路由）：[LLM 推理缓存与 KV Cache 管理](/04-llmops/kv-cache/)（已上线）
- 想了解 AI 集群网络（NVLink/UALink、IB/RoCE/UEC、Rail-optimized 拓扑）：[AI 集群网络](/02-cloud-native/ai-networking/)（已上线）
- 想了解 GraphRAG 与知识图谱检索（GraphRAG/LightRAG/HippoRAG、社区摘要、多跳查询）：[GraphRAG 与知识图谱检索](/06-rag/graphrag/)（已上线）
- 想了解模型量化与压缩基础设施（GPTQ/AWQ/NVFP4、校准到部署管线）：[模型量化与压缩基础设施](/04-llmops/model-quantization/)（已上线）
- 想了解多模态与语音推理基础设施（VLM 推理、Realtime 语音、打断与双工）：[多模态与语音推理基础设施](/04-llmops/multimodal-inference/)（已上线）
- 想了解端侧与边缘推理基础设施（llama.cpp/MLX/ExecuTorch、内存受限解码、异构调度与端云协同）：[端侧与边缘推理基础设施](/04-llmops/edge-inference/)（已上线）
- 想了解 AI SRE：[AI SRE](/07-ai-sre/)（已上线）
- 想了解 Benchmark + Evaluation（Agent / LLM / RAG 可复现评测框架）：[Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/)（已上线）
- 想了解安全：[安全](/08-security/)（已上线）
- 想了解 OpenAI 基础设施案例：[OpenAI 案例研究](/09-case-study/openai/)（已上线）
- 想了解 Anthropic 基础设施案例：[Anthropic 案例研究](/09-case-study/anthropic/)（已上线）
- 想了解 Meta 基础设施案例：[Meta 案例研究](/09-case-study/meta/)（已上线）
- 想了解 Google 基础设施案例：[Google 案例研究](/09-case-study/google/)（已上线）
- 想了解 DeepSeek 基础设施案例（DualPipe/FP8/MLA/3FS）：[DeepSeek 案例研究](/09-case-study/deepseek/)（已上线）
- 想了解 xAI 基础设施案例（Memphis Colossus）：[xAI 案例研究](/09-case-study/xai/)（已上线）
- 想了解 Perplexity 推理经济学案例（答案引擎、Sonar、模型路由）：[Perplexity 案例研究](/09-case-study/perplexity/)（已上线）

### 3. 每个主题的结构

每个主题都按照统一结构组织：

1. 背景（Motivation）
2. 核心思想（Core Concepts）
3. 架构设计（Architecture）
4. Runtime 工作流程
5. 核心模块
6. 源码分析
7. 工程实践（Mini Demo）
8. 企业生产实践
9. 最佳实践
10. 面试题
11. 延伸阅读

## 内容标准

本手册遵循以下原则：

- **工程化 > 原理化 > 系统化 > 可实践 > 可维护**
- 不翻译官方文档，不堆砌 API
- 每个结论都需要有来源，优先引用官方文档、论文、源码、生产实践
- 大量使用 Mermaid 图表解释架构与流程
- 每个主题都包含可运行的 Mini Demo

## 如何贡献

1. 在 GitHub 上提交 Issue 反馈问题或建议
2. 提交 PR 补充内容、修复错误、更新链接
3. 遵循统一的章节结构与文档风格

## 交叉引用约定

- 同一章节的子页面使用相对路径，例如 `[下一节](02-core-ideas)`
- 跨章节引用使用绝对路径，例如 `[学习路线](/10-roadmap/learning-path)`
- 外部链接使用完整 URL

## 声明

本手册内容仅供学习交流，所有引用均已注明来源。如有遗漏或错误，欢迎指正。
