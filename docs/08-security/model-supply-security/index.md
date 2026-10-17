# AI 供应链与模型安全

大模型的"原材料"和"出厂物流"正在被武器化。Hugging Face 上持续出现嵌有反弹 shell 的恶意模型，pickle 反序列化即远程代码执行；RLHF 数据里可以埋入只在触发时出现的后门；MCP 工具描述里可以塞进模型可见、用户不可见的隐藏指令；而训练完成的模型本身——权重、Tokenizer、API 服务——又会遭遇窃取、蒸馏抽取与未授权分发。AI 供应链与模型安全主题聚焦这条"从数据到权重到工具到运行时"的完整链路：每一环的完整性怎么保证、投毒怎么检测、资产怎么保护、合规时间表怎么对齐。

## 一句话理解

> AI 供应链安全要回答三个问题：**进来的东西是谁给的（provenance）、有没有被改过（integrity）、出事之后能不能定位与回滚（attribution & response）**——模型资产安全再加一个：**别人偷走之后能不能证明是你的（watermark & fingerprint）**。

## 学习目标

读完本主题后，你应该能够：

- 解释 pickle 反序列化为什么会变成 RCE，safetensors 为什么"格式安全但不解决权重后门"，以及 torch 2.6 之后 `torch.load` 默认行为发生了什么变化。
- 设计模型工件的签名-验证链：merkle 清单、Sigstore/cosign 实践、Model Registry 准入扫描的门禁位置。
- 说清楚 Hugging Face 的安全机制边界：ClamAV 恶意软件扫描、pickle import 扫描、Gated Repo——以及各自防不住什么。
- 分析训练数据投毒与后门攻击（投毒 RLHF、Sleeper Agents）的检测思路：canary 触发率、行为评测、异常权重检测，以及为什么"没有银弹"。
- 拆解 MCP 工具供应链的 tool poisoning 与 rug pull 攻击面，设计工具清单完整性校验与注册管控。
- 为 Agent 代码执行选择沙箱模型（Firecracker / gVisor / E2B），并理解 egress 控制与 prompt injection 的传导关系。
- 部署模型资产保护：成员推断与模型抽取的防御、权重水印与指纹的原理与局限。
- 对齐合规时间线：EU AI Act GPAI 义务（2026-08 强制执行）、NIST AI RMF、ISO/IEC 42001、中国 AI 生成内容标识办法。

## 与相邻主题的关系

| 相邻主题 | 与本主题的关系 |
|---|---|
| [安全篇](/08-security/) | 安全篇覆盖 IAM/Secrets/零信任/Guardrails/合规框架的总体系；本主题深挖其中"供应链 + 模型资产"这条线，不重复展开身份与网关。 |
| [Personal AI Agent](/05-agent/personal-agent/) | 个人 Agent 是 MCP 工具投毒与本地执行风险的最高暴露面，其工具安装策略直接复用本主题的清单校验方法。 |
| [MCP](/05-agent/mcp/) | MCP 讲协议与生态；本主题讲 MCP Server 作为"可执行依赖"的供应链管控：注册、锁定、完整性。 |
| [Agent Runtime](/05-agent/agent-runtime/) | Runtime 是沙箱执行与 egress 控制的落地层，本主题给出威胁模型与选型依据。 |
| [向量数据库](/06-rag/vector-db/) | 向量库是 RAG 的数据底座，其索引与片段同样存在投毒与完整性问题（OWASP LLM08）。 |
| [MLflow](/03-ai-platform/mlflow/) | Model Registry 是签名验证与扫描门禁的天然挂载点。 |
| [模型量化](/04-llmops/model-quantization/) | GGUF/量化是分发格式，其供应链视角（格式安全、来源验证）与本主题互补。 |
| [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/) | 后门检测与模型审计依赖行为评测方法论与防污染纪律。 |

## 章节导航

1. [背景与动机：当"下载一个模型"变成供应链事件](01-background)
2. [核心概念：信任边界、工件完整性与投毒的统计学本质](02-core-ideas)
3. [架构设计：AI 供应链安全分层防御体系](03-architecture)
4. [供应链全流程：从数据源到生产加载的门禁点](04-supply-chain-workflow)
5. [核心模块：工件扫描、签名验证、数据去毒、MCP 管控、沙箱与水印](05-core-modules)
6. [生态与实现分析：HF 安全机制、扫描器、Sigstore、MCP Registry、沙箱对比](06-ecosystem-analysis)
7. [Mini Demo：纯 Python 实现供应链安全最小闭环](07-mini-demo)
8. [企业生产实践：注册中心门禁、红队与事件响应](08-production-practice)
9. [最佳实践：检查清单与反模式](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 一句话总结

AI 供应链安全把传统软件供应链的"签名、扫描、锁定、审计"四件套翻译成模型时代的语言：pickle 是要扫描的依赖，safetensors 是要推行的格式，Model Registry 是要设卡的高速口，MCP 工具是要锁版本的 npm 包，水印是模型被盗后最后的法庭证据——而所有机制的落地都服从同一个原则：**在加载之前验证，在授权时锁定，在运行时隔离，在泄露后可举证**。
