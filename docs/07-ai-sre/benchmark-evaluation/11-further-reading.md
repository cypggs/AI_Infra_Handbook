# 延伸阅读

本章整理 Benchmark + Evaluation 领域的经典论文、开源工具与官方文档，并给出本手册内部的跨主题链接，帮助读者构建完整的知识体系。

## 经典论文

### 综合能力评测

- **HELM: Holistic Evaluation of Language Models**  
  提出全面评估语言模型的框架，覆盖准确性、校准、鲁棒性、公平性、效率、偏见、毒性等维度。是设计多维评估体系的必读文献。

- **MMLU: Measuring Massive Multitask Language Understanding**  
  涵盖 57 个学科的知识问答 benchmark，广泛用于基础模型能力对比。

### 代码与推理

- **HumanEval: Evaluating Large Language Models Trained on Code**  
  OpenAI 提出的代码生成 benchmark，通过单元测试验证代码正确性，是 Pass@k 指标的来源。

- **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?**  
  用真实 GitHub issue 与 PR 测试模型端到端修 bug 的能力，是 Agent / 工具使用评估的重要参考。

### Agent 与工具

- **AgentBench: Evaluating LLMs as Agents**  
  系统评估 LLM 在多环境（OS、数据库、知识图谱、购物等）中作为 Agent 的表现。

- **ToolBench / APIBench**  
  评估模型调用真实 API 的能力，覆盖工具选择、参数填充、结果处理。

### RAG 评估

- **RAGAS 相关论文**  
  提出 Faithfulness、Answer Relevancy、Context Precision / Recall 等指标，是 RAG 评估的事实标准。

- **REPLUG 与 Retrieve-then-Read 系列**  
  讨论检索与生成联合评估的方法。

### 安全与红队

- **Red Teaming Language Models with Language Models**  
  用模型自动生成对抗性 prompt，用于安全评估。

- **Jailbreak and Prompt Injection Literature**  
  关注越狱、提示注入、数据提取等攻击形式的评估与防御。

## 开源工具与文档

| 工具 | 文档 / 仓库 |
|---|---|
| OpenAI Evals | https://github.com/openai/evals |
| EleutherAI LM Evaluation Harness | https://github.com/EleutherAI/lm-evaluation-harness |
| LangSmith | https://docs.smith.langchain.com |
| Phoenix / Arize | https://docs.arize.com/phoenix |
| Weave | https://weave-docs.wandb.ai |
| Ragas | https://docs.ragas.io |
| DeepEval | https://docs.confident-ai.com |
| Promptfoo | https://www.promptfoo.dev/docs |
| MLflow Evaluate | https://mlflow.org/docs/latest/llms/llm-evaluate/index.html |
| OpenTelemetry GenAI Semantic Conventions | https://opentelemetry.io/docs/specs/semconv/gen-ai/ |

## 跨主题链接

Benchmark + Evaluation 与手册中多个主题紧密相关：

- [AI SRE](/07-ai-sre/)：提供可观测性、SLO、告警与事故响应基础，是 EvalOps 的底座。
- [Agent Runtime](/05-agent/agent-runtime/)：Agent 的多步骤执行需要 trace-based 评估来逐层验证。
- [Tool Use](/05-agent/tool-use/)：工具选择、参数填充、返回值处理是评估的核心维度。
- [MCP](/05-agent/mcp/)：统一工具协议让工具调用评估更具标准化基础。
- [RAG](/06-rag/)：RAG 的检索与生成质量需要专门的 benchmark 与指标。
- [LLMOps](/04-llmops/)：模型版本、Prompt、实验管理为评估提供变更上下文。
- [Security](/08-security/)：安全评估、红队、越狱测试是 Benchmark + Evaluation 不可或缺的子集。

## 推荐学习路径

1. 先读本主题 [01-background](01-background) 与 [02-core-ideas](02-core-ideas)，建立概念框架。
2. 阅读 HELM 论文，理解多维评估设计思想。
3. 实践一个开源工具：推荐从 [Ragas](https://docs.ragas.io)（RAG）或 [DeepEval](https://docs.confident-ai.com)（通用 LLM 评估）入手。
4. 结合 [AI SRE](/07-ai-sre/) 学习 OpenTelemetry 与可观测性集成。
5. 深入一个生产案例：用影子评估验证模型升级，或把评估接入 CI Gate。

## 一句话总结

Benchmark + Evaluation 是连接 AI 能力、可观测性、产品价值与安全合规的桥梁；持续阅读、实践与校准，是让评估体系保持生命力的关键。
