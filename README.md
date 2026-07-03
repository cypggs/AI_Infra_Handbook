# AI Infra Handbook

面向 AI Infrastructure 工程师的开源中文知识库。

> 目标：打造中文最完整、最系统、最工程化的 AI Infrastructure 学习体系。

[![Deploy](https://img.shields.io/badge/Deploy-Vercel-black?logo=vercel)](https://ai-infra-handbook.vercel.app)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

## 在线阅读

**[https://ai-infra-handbook.vercel.app](https://ai-infra-handbook.vercel.app)**

## 项目定位

这不是博客，不是文章合集，不是官方文档翻译，也不是 AI 总结。

这是一本长期维护的**工程 Handbook**，帮助一名有 Kubernetes / Linux 基础的工程师成长为能够设计和构建 AI 基础设施的平台工程师。

## 目标读者

- AI Infra Engineer
- AI Platform Engineer
- LLMOps Engineer
- AI SRE
- Platform Engineer
- Staff Engineer
- 架构师

## 内容标准

每个主题都按照统一结构执行：

```
Research → Understand → Architecture → Source Code → Engineering Practice
    → Production Experience → Best Practice → Interview → Documentation
```

每个主题包含 11 个章节：

1. 背景
2. 核心思想
3. 架构设计
4. Runtime 工作流程
5. 核心模块
6. 源码分析
7. 工程实践（Mini Demo）
8. 企业生产实践
9. 最佳实践
10. 面试题
11. 延伸阅读

## 目录结构

```
docs/
├── 01-foundation/      # Linux、网络、存储、GPU、分布式系统
├── 02-cloud-native/    # Docker、Kubernetes、Helm、Operator
├── 03-ai-platform/     # Kubeflow、KServe、Ray、MLflow
├── 04-llmops/          # vLLM、SGLang、TensorRT-LLM、Triton Inference Server、LLM Gateway
├── 05-agent/           # Agent Runtime、Memory、Multi-Agent、Reflection、MCP、Planning
├── 06-rag/             # Embedding、Retriever、Hybrid Search、GraphRAG
├── 07-ai-sre/          # OpenTelemetry、Observability、AIOps、SLO
├── 08-security/        # IAM、Secrets、Zero Trust、合规
├── 09-case-study/      # OpenAI、Anthropic、Cursor、Perplexity 等
└── 10-roadmap/         # 学习路线、面试指南、术语表
```

## 本地开发

```bash
pnpm install
pnpm docs:dev
```

构建：

```bash
pnpm docs:build
```

预览构建产物：

```bash
pnpm docs:preview
```

## 已上线主题

- [vLLM 详解](docs/04-llmops/vllm/) — 覆盖 V1 引擎、PagedAttention、Continuous Batching、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [SGLang 详解](docs/04-llmops/sglang/) — 覆盖 LLM Program、RadixAttention、Structured Generation、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [TensorRT-LLM 详解](docs/04-llmops/tensorrt-llm/) — 覆盖 NVIDIA 编译型推理引擎、Builder/Engine/Runtime/Executor、In-flight Batching、Plugin、量化、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [Triton Inference Server 详解](docs/04-llmops/triton/) — 覆盖多框架推理服务、Model Repository、Backend 抽象、Dynamic/Sequence/Ensemble 调度、BLS、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [LLM Gateway 详解](docs/04-llmops/llm-gateway/) — 覆盖访问控制与抽象层、Provider 抽象、统一 OpenAI-compatible API、路由、负载均衡、限流、重试降级、认证、请求/响应转换、成本追踪、可观测、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [Agent Runtime 详解](docs/05-agent/agent-runtime/) — 覆盖 ReAct 循环、工具注册与 function calling、记忆、状态机、护栏、可观测、恢复、与 LLM Gateway 集成、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Memory 详解](docs/05-agent/memory/) — 覆盖 Agent 记忆系统、工作记忆、短期记忆、长期语义记忆、episodic 记忆、向量检索、存储后端、与 Agent Runtime 集成、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Multi-Agent 详解](docs/05-agent/multi-agent/) — 覆盖多 Agent 协作、角色定义、消息通信、协调调度、共享黑板、团队可观测、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Reflection 详解](docs/05-agent/reflection/) — 覆盖 Agent 自我反思与纠错、生成—批判—评估—修订闭环、Generator/Critic/Evaluator/Revision Controller/Workspace/Observer、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [MCP 详解](docs/05-agent/mcp/) — 覆盖 Model Context Protocol、Host/Client/Server 角色、Tools/Resources/Prompts、JSON-RPC 协议流程、Capability negotiation、Transport（stdio/SSE/HTTP）、官方 SDK 源码、Mini Demo、企业生产实践与面试题（内容更新至 2026-07-03）
- [Planning 详解](docs/05-agent/planning/) — 覆盖 Agent 规划系统、任务分解范式、计划表示（列表/DAG/树/状态图）、Plan-Execute-Observe-Replan 循环、动态重规划、与 Runtime/Memory/Reflection/Multi-Agent/MCP 集成、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）

## 内容更新说明

- 本手册优先引用官方文档、论文、源码与生产实践，避免依赖过时第三方内容。
- vLLM 主题已基于 2026 年中主分支（默认 V1 引擎）进行更新。
- SGLang 主题已基于 2026 年 7 月 v0.5.14 进行更新。

## 贡献

欢迎提交 Issue 和 PR。请遵循统一的章节结构与文档风格。

## License

[CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
