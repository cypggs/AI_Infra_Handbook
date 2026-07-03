# 学习路线

本路线面向已经具备 Kubernetes / Linux 基础，希望成长为 AI Infrastructure 工程师的读者。

## 阶段一：夯实基础（4~8 周）

目标：建立 AI 基础设施所需的底层知识。

- Linux 系统调优与性能分析
- 计算机网络（TCP/IP、RDMA、NCCL 网络拓扑）
- 存储系统（本地存储、对象存储、并行文件系统）
- GPU 架构与 CUDA 基础
- 分布式系统基础（一致性、容错、通信）

## 阶段二：掌握云原生（4~6 周）

目标：能够在 Kubernetes 上构建和运维平台。

- Docker 与容器运行时
- Kubernetes 核心资源与调度
- Helm 与 Operator
- CRI、CNI、CSI
- GPU 在 Kubernetes 上的调度（NVIDIA Device Plugin、GPU Operator）

## 阶段三：AI 平台与 LLMOps（6~10 周）

目标：理解模型训练、推理、服务的完整链路。

- **[Ray](/03-ai-platform/ray/)（已上线）** / MLflow
- 模型服务与推理优化
- **[vLLM（已上线）](/04-llmops/vllm/)**
- **SGLang（已上线）**
- **TensorRT-LLM（已上线）**
- **Triton Inference Server（已上线）**
- **LLM Gateway（已上线）**

## 阶段四：Agent 与 RAG（4~6 周）

目标：理解大模型应用的基础设施需求。

- **Agent Runtime（已上线）**
- **Memory（已上线）**
- **Multi-Agent（已上线）**
- **Reflection（已上线）**
- **[MCP](/05-agent/mcp/)（已上线）**
- **[Planning](/05-agent/planning/)（已上线）**
- **[Tool Use](/05-agent/tool-use/)（已上线）**
- **[Agent OS](/05-agent/agent-os/)（已上线）**
- **[RAG](/06-rag/)（已上线）**
- Embedding、Retriever、Hybrid Search
- GraphRAG 与评估体系

## 阶段五：AI SRE 与安全（持续）

目标：让 AI 系统在生产环境中稳定、安全、可观测。

- **[AI SRE](/07-ai-sre/)（已上线）**
- **[安全](/08-security/)（已上线）**
- OpenTelemetry 与可观测性
- SLO / Error Budget
- AIOps 与事件响应
- IAM、Secrets、Zero Trust
- 合规（SOC2、HIPAA、GDPR）

## 阶段六：案例研究（持续）

目标：从真实公司的工程实践中提炼可复用的设计原则。

- **[OpenAI 案例研究](/09-case-study/openai/)（已上线）** — 训练/推理基础设施、模型安全与对齐、产品化工程经验
- **[Anthropic 案例研究](/09-case-study/anthropic/)（已上线）** — 宪法对齐/RLAIF、机制可解释性、Trainium/Colossus 异构算力、prompt caching 与 RSP/ASL 治理
- **[Meta 案例研究](/09-case-study/meta/)（已上线）** — 开放权重、OCP 硬件协同设计（Grand Teton/Catalina/MTIA）、RoCE/InfiniBand 双网络织物、SDC 治理与 >95% 有效训练时间、Llama Stack
- **[Google 案例研究](/09-case-study/google/)（已上线）** — TPU 自研硅（MXU/SparseCore/3D-torus/OCS）、NSDI'24 双路径恢复（99.98% 可用率）、GSPMD/Pathways 自动并行、Falcon 硬件传输、开放软件栈（JAX/XLA/MaxText）+ 闭源硬件
- Cursor、Perplexity 等持续建设中

## 推荐学习顺序

如果你时间有限，建议按以下优先级：

1. [vLLM](/04-llmops/vllm/) — 理解 LLM 推理的核心挑战
2. [SGLang](/04-llmops/sglang/) — 理解 LLM Program、RadixAttention 与结构化生成
3. [TensorRT-LLM](/04-llmops/tensorrt-llm/) — 理解 NVIDIA 编译型推理引擎与生产部署
4. Kubernetes 与 GPU 调度 — 理解 AI 平台的底座
5. **[Ray](/03-ai-platform/ray/)** — 理解分布式 AI 计算
6. OpenTelemetry — 理解 AI 系统可观测性
7. [LLM Gateway](/04-llmops/llm-gateway/) — 理解多供应商/多引擎的统一接入层
8. [Agent Runtime](/05-agent/agent-runtime/) — 理解 Agent 时代的执行容器与 ReAct 循环
9. [Memory](/05-agent/memory/) — 理解 Agent 的记忆系统与长期上下文管理
10. [Multi-Agent](/05-agent/multi-agent/) — 理解多 Agent 协作、角色定义与协调调度
11. [Reflection](/05-agent/reflection/) — 理解 Agent 自我反思、批判与质量提升闭环
12. [MCP](/05-agent/mcp/) — 理解 Agent 协议、工具发现与跨模型能力复用
13. [Planning](/05-agent/planning/) — 理解 Agent 任务分解、计划表示与动态重规划
14. [Tool Use](/05-agent/tool-use/) — 理解 Agent 工具调用、Schema、解析、执行与可观测
15. [Agent OS](/05-agent/agent-os/) — 理解 Agent 运行时操作系统、进程调度、沙箱、Workspace 与多 Agent 治理
16. [RAG](/06-rag/) — 理解外部知识检索、向量索引、混合检索与检索增强生成
17. [AI SRE](/07-ai-sre/) — 理解 AI 系统可观测性、SLO、AIOps 与事故响应
18. [安全](/08-security/) — 理解 AI 系统身份、密钥、零信任、Guardrails、合规与事件响应
19. [OpenAI 案例研究](/09-case-study/openai/) — 通过 OpenAI 的演化理解训练/推理基础设施、安全对齐与产品化工程落地
20. [Anthropic 案例研究](/09-case-study/anthropic/) — 通过 Anthropic 理解宪法对齐、机制可解释性、异构算力、prompt caching 与 RSP/ASL 安全治理
21. [Meta 案例研究](/09-case-study/meta/) — 通过 Meta 理解开放权重、硬件协同设计、双网络织物、同步训练可靠性（SDC 治理/>95% 有效训练时间）与 MTIA 自研硅
22. [Google 案例研究](/09-case-study/google/) — 通过 Google 理解 TPU 自研硅、OCS 可重配拓扑、NSDI'24 双路径恢复、GSPMD/Pathways 编译器自动并行与开放软件栈

## 面试准备

参考 [面试指南](/10-roadmap/interview-guide)。
