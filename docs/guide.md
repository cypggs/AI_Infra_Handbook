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

- 想了解 LLM 推理引擎：从 [vLLM](/04-llmops/vllm/)、[SGLang](/04-llmops/sglang/)、[TensorRT-LLM](/04-llmops/tensorrt-llm/)、[Triton Inference Server](/04-llmops/triton/) 或 [LLM Gateway](/04-llmops/llm-gateway/) 开始
- 想了解 Agent Runtime：[Agent Runtime](/05-agent/agent-runtime/)（已上线）
- 想了解 Agent Memory：[Memory](/05-agent/memory/)（已上线）
- 想了解 Agent 协议：[MCP](/05-agent/)（建设中）
- 想了解 AI 可观测性：[OpenTelemetry](/07-ai-sre/)（建设中）

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
