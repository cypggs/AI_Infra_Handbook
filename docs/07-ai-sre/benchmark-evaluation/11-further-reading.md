# 延伸阅读

本章整理 Benchmark + Evaluation 领域的经典论文、开源工具与官方文档，并给出本手册内部的跨主题链接，帮助读者构建完整的知识体系。

## 经典论文

### 综合能力评测

- **HELM: Holistic Evaluation of Language Models**  
  提出全面评估语言模型的框架，覆盖准确性、校准、鲁棒性、公平性、效率、偏见、毒性等维度。是设计多维评估体系的必读文献。

- **MMLU: Measuring Massive Multitask Language Understanding**  
  涵盖 57 个学科的知识问答 benchmark，广泛用于基础模型能力对比。注意：已接近饱和，且存在错标问题。

- **MMLU-Pro / MMLU-Redux**  
  MMLU-Pro 用 10 选项与更难题目加难 MMLU；MMLU-Redux 修正了原基准中的错标题目，是引用 MMLU 分数时的更干净替代品。

- **GPQA Diamond**：研究生级"Google -proof"问答，前沿模型已趋于饱和，仍广泛用于推理能力对比。

- **Humanity's Last Exam (HLE)**：约 2500 道跨学科极难题，2025 年初前沿模型仅 20% 上下，是当前的区分度天花板基准之一。

- **LiveBench**（ICLR 2025 Spotlight）：每月轮换题目、保留私有污染免疫子集的动态基准，是校验静态榜单的"校准锚"。

### 代码与推理

- **HumanEval: Evaluating Large Language Models Trained on Code**  
  OpenAI 提出的代码生成 benchmark，通过单元测试验证代码正确性，是 Pass@k 指标的来源。

- **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?**  
  用真实 GitHub issue 与 PR 测试模型端到端修 bug 的能力。注意后续版本差异：Verified（500 题精选）、Pro（1865 道长程任务）、Multimodal（前端多模态任务），且分数强烈依赖 scaffold。

- **FrontierMath**（Epoch AI）：研究级数学难题集，o3 仅约 25%，是当前最重要的未饱和数学基准。

- **ARC-AGI-2**：抽象推理基准，专门测"没见过题型时的泛化"，对人类容易、对模型极难；ARC Prize 2025 技术报告值得阅读。

- **SWE-bench 审计与 "State-of-the-Art Claims Require State-of-the-Art Evidence"（2026）**：讨论榜单证据标准与公开 split 缺陷，引用 SWE-bench 分数前必读。

### Agent 与工具

- **AgentBench: Evaluating LLMs as Agents**  
  系统评估 LLM 在多环境（OS、数据库、知识图谱、购物等）中作为 Agent 的表现。

- **GAIA**：通用 AI 助手基准，分三级难度，测多步推理与工具使用；看榜单时注意 Level 3 才是真实区分度。

- **τ-bench / τ²-bench**（Sierra）：客服场景多轮对话评测，核心贡献是 pass^k 可靠性度量与"用户 + 工具"双模拟器。

- **BFCL v4**（Berkeley Function-Calling Leaderboard）：函数调用正确性（AST 匹配）+ 多轮 + Agentic 类别（web search、memory），是工具调用能力的标准刻度。

- **BrowseComp**（OpenAI）：测量 Agent 在海量网页中"坚持找"冷门信息的 browsing 基准。

- **OSWorld / OSWorld 2.0**：计算机操作基准，2.0 版转向 108 道长程真实任务，前沿模型二元完成率仅约 20%，是 computer-use 能力的清醒剂。

- **Agent-as-a-Judge**（ICML 2025）：让评审 Agent 逐步检查被评 Agent 轨迹，一致率约 90% 且成本降约 97%。

### 长上下文评测

- **HELMET**（ICLR 2025）：指出 NIAH 类探针对真实长上下文能力预测力差，给出 RAG、引用、重排、many-shot 等 7 类应用化评测。

- **LongBench v2**：8K-2M 词的真实长文档多选基准（人类专家基线约 53.7%），比合成探针更接近生产场景。

### RAG 评估

- **RAGAS 相关论文**  
  提出 Faithfulness、Answer Relevancy、Context Precision / Recall 等指标，是 RAG 评估的事实标准。

- **REPLUG 与 Retrieve-then-Read 系列**  
  讨论检索与生成联合评估的方法。

### 评测治理：污染、刷榜与 Judge 安全

- **The Leaderboard Illusion**（arXiv:2504.20879，2025）：系统揭露 LMArena 类众包榜的变体挑选、静默下架等结构性偏差。
- **LessLeak-Bench**（2025）：对 83 个软件工程基准的数据泄漏调查。
- **One Token to Fool LLM-as-a-Judge**（NeurIPS 2025）：judge 的对抗攻击面研究。
- **LLM-Based Agent Primer / Meta-Judging with LLMs（2025-2026）**：judge 可靠性的分解式审计方法。

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
| OpenCompass | https://github.com/open-compass/opencompass |
| Inspect AI（UK AISI） | https://inspect.aisi.org.uk |
| LangSmith | https://docs.smith.langchain.com |
| Phoenix / Arize | https://docs.arize.com/phoenix |
| Weave | https://weave-docs.wandb.ai |
| Ragas | https://docs.ragas.io |
| DeepEval | https://docs.confident-ai.com |
| Promptfoo | https://www.promptfoo.dev/docs |
| MLflow Evaluate | https://mlflow.org/docs/latest/llms/llm-evaluate/index.html |
| OpenTelemetry GenAI Semantic Conventions | https://opentelemetry.io/docs/specs/semconv/gen-ai/ |
| LiveBench | https://livebench.ai |
| LMArena | https://lmarena.ai |

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
