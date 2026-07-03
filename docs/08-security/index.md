# 安全篇

AI 系统的安全不只是“防火墙 + WAF”的边界防御。模型权重、训练数据、提示词、Agent 工具链、向量库、API Key、非人类身份（Non-Human Identity）共同构成了一个比传统 Web 应用更复杂的攻击面。安全篇的目标，是帮助 AI Infra 工程师建立覆盖身份、网络、运行时、数据、模型与合规的完整安全体系。

## 一句话理解

> AI 基础设施的安全，是在“模型、数据、Agent、人”之间建立最小权限、可审计、可回滚的信任边界。

## 学习目标

读完本主题后，你应该能够：

- 识别 AI 系统相比传统软件的独有攻击面（提示注入、模型窃取、数据外泄、工具滥用等）。
- 设计覆盖身份认证、授权、密钥管理、零信任网络、输入输出过滤的 AI 安全架构。
- 为 LLM/Agent/RAG 服务选择并集成合适的开源安全工具（OPA、OpenFGA、Vault、SPIRE、Presidio、Guardrails 等）。
- 建立合规、隐私治理与审计日志体系，满足 GDPR、AI Act、SOC2 等要求。
- 制定 AI 安全事件响应、红队测试与供应链安全流程。

## 与相邻主题的关系

| 相邻主题 | 与安全的关系 |
|---|---|
| [LLM Gateway](/04-llmops/llm-gateway/) | Gateway 是统一安全策略执行点：认证、限流、密钥隔离、审计、内容过滤。 |
| [Agent Runtime](/05-agent/agent-runtime/) | Agent 循环中的工具调用需要最小权限与行为护栏，Runtime 是权限落地层。 |
| [RAG](/06-rag/) | 向量库与检索片段可能包含 PII 或敏感知识，需要访问隔离、脱敏与审计。 |
| [AI SRE](/07-ai-sre/) | 安全事件是可观测性的一部分；trace、metrics、audit log 是检测与溯源的基础。 |
| [MCP](/05-agent/mcp/) | MCP Server 暴露的工具/资源/提示需要 capability 协商与调用授权。 |
| [Tool Use](/05-agent/tool-use/) | 工具调用是 Agent 越权与数据外泄的高危路径，需要 schema 校验与沙箱执行。 |

## 章节导航

1. [背景：为什么 AI 系统需要专门的安全体系](01-background) — 攻击面演进、关键威胁、合规驱动。
2. [核心思想](02-core-ideas) — CIA + 安全、最小权限、纵深防御、零信任、安全左移、非人类身份。
3. [架构设计](03-architecture) — 分层安全架构、控制面与数据面、边界安全 vs 零信任。
4. [AI 安全生命周期](04-security-lifecycle) — 从设计、开发、训练、部署到运营与事件响应的全流程。
5. [核心模块](05-core-modules) — IAM、策略引擎、密钥管理、安全网关、Guardrails、网络策略、数据治理、模型扫描、审计。
6. [源码与生态分析](06-source-analysis) — OPA、OpenFGA、Vault、SPIRE、Istio、Presidio、Llama Guard、Sigstore 等对比。
7. [Mini Demo](07-mini-demo) — 一个纯标准库的 AI 安全网关示例：API Key、RBAC、提示注入检测、PII 脱敏、审计日志。
8. [企业生产实践](08-production-practice) — 多租户隔离、零信任落地、红队、合规审计、事件响应。
9. [最佳实践](09-best-practices) — 检查清单与常见反模式。
10. [面试题](10-interview-questions) — 初/中/高级 AI 安全面试题。
11. [延伸阅读](11-further-reading) — 论文、法规、官方文档与交叉引用。

## 一句话总结

AI 安全是一个贯穿模型、数据、运行时、网络、身份与合规的体系工程：最小权限是手段，可审计是底线，零信任是架构原则，红队与持续运营是保障。
