# Perplexity 案例研究

如果说 OpenAI 的故事是"把规模做到极致并产品化"、Anthropic 的故事是"把安全写进模型全生命周期"、xAI 的故事是"用组织速度替代工程从容"、DeepSeek 的故事是"用算法—系统协同设计换算力"，那么 Perplexity 的故事代表了另一种同样深刻的范式：**不训练基础模型，靠推理经济学取胜**——把每一毫秒的延迟、每一分钱的推理成本、每一次检索的质量都当成产品本身来经营。

Perplexity 是"答案引擎（Answer Engine）"品类的开创者：用户提问，它不返回十条蓝色链接，而是直接生成带来源引用的答案。这个产品在 2023 年用约 8 个人的团队起步，三年多时间里把查询量做到月十亿级、年收入做到数亿美元（均为公开报道口径），同时与 Google 的 AI Overviews、OpenAI 的 ChatGPT Search 正面竞争。它的基础设施故事围绕一个核心问题展开：**当模型可以从别人那里租来时，什么才是真正的护城河？Perplexity 的答案是速度、索引和迭代速度。**

研究 Perplexity 的价值还在于它的"坦白"：这家公司没有 NSDI 论文，也没有超大规模训练集群可讲。它的公开材料主要是官方博客、产品文档、CEO Aravind Srinivas 的大量访谈，以及 2026 年密集发布的一批工程博客（Photon 检索引擎、CobbleDB 存储、SPACE 沙箱开源）。**本主题自始至终严格区分三种信息：一手公开材料（官方博客/文档/官宣）、媒体报道与访谈转述（标注来源）、以及明确未公开的部分（绝不编造架构细节）。**

## 一句话理解

> Perplexity 的基础设施故事，是用 **推理经济学（不训基础模型，把推理成本与延迟当产品经营）+ 速度即产品（tail latency 哲学，TTFT 与流式渲染优先）+ 模型无关主义（哪家模型好就用哪家，自研只做推理专用的轻量微调）+ 自建检索基建（PerplexityBot 爬虫 → Photon 检索引擎 → CobbleDB 热存储的三级栈）** 四条主线，回答"不拥有最强模型时如何赢"的工程实践史。

## 学习目标

读完本主题后，你应该能够：

- 复述 Perplexity 的产品与模型演进时间线：2022-12 成立（4 位创始人、约 8 人早期团队）→ 2023 年答案引擎上线 → 2024 年 Pro Search / Pro 订阅 / Sonar API 发布 → 2025 年 Deep Research / Comet 浏览器 / Labs → 2026 年 Computer / Agent API / Sonar API 退役。
- 解释**推理经济学**的成本结构：单次查询成本 = 检索成本 + 生成成本（TTFT × 算力单价 + token 数 × 单价），以及为什么"速度"在这个公式里既是分子也是分母（[第 2 章](02-core-ideas)、[Mini Demo 场景 5](07-mini-demo)）。
- 解释 **tail latency 哲学**：对搜索与生成每一层都追踪 P90/P99（借自 Google "The Tail at Scale"），以及流式渲染如何把"等整段答案"变成"等第一个词元"（[Mini Demo 场景 3](07-mini-demo)）。
- 拆解 **Sonar 模型策略**：以 Llama 3/3.3 为基座做后训练（摘要、引用、上下文保持），在 Cerebras CS-3 晶圆级引擎上做到约 1200 token/s 的官方口径，与"租 GPT/Claude/Gemini"的模型无关路线并行不悖。
- 理解 2026 年公开的三件自建基建：**Photon**（检索/排序引擎，p99 从约 800 ms 降到 65 ms）、**CobbleDB**（替换 DynamoDB 的热存储，batch read 延迟降 82%）、**SPACE**（Agent 沙箱，已开源，每天数百万次创建）。
- 评估它的风险面：与内容出版商的版权诉讼战（Forbes、Wired、NYT、Dow Jones、大英百科）、Amazon 对 Comet 的诉讼、以及"模型供应商既是伙伴又是竞争者"的结构性张力。

## 与相邻主题的关系

| 相邻主题 | 与 Perplexity 案例的关系 |
|---|---|
| [OpenAI 案例研究](/09-case-study/openai/) | 对照"训练巨型基础模型并产品化"与"不训模型、把推理经济学做到极致"；OpenAI 既是其供应商（GPT 系列）也是其竞争者（ChatGPT Search）。 |
| [DeepSeek 案例研究](/09-case-study/deepseek/) | 对照"用算法创新把训练与推理成本同时打下来"与"租模型 + 自建检索栈"；r1-1776 是两家开源合作的直接产物（DeepSeek 基座 + Perplexity 后训练）。 |
| [xAI 案例研究](/09-case-study/xai/) | 对照"百万卡训练集群"与"零训练集群"；xAI 的 Grok 也是 Perplexity 接入的第三方模型之一。 |
| [Google 案例研究](/09-case-study/google/) | Perplexity 的挑战对象：AI Overviews/Gemini 是"搜索巨头 AI 化"，Perplexity 是"AI 原生搜索"；Google 同时是其云与模型合作伙伴（报道口径）。 |
| [RAG](/06-rag/) | Perplexity 是生产级 RAG 的最完整公开案例之一：检索、重排、引用、防幻觉的产品化实现。 |
| [向量数据库与 Embedding 基础设施](/06-rag/vector-db/) | CobbleDB / Photon 说明 AI 搜索的存储不止向量库：倒排 + KV + 对象存储的分层栈。 |
| [LLM Gateway](/04-llmops/llm-gateway/) | Perplexity 的模型无关主义是多模型路由网关的极端案例：Sonar、GPT、Claude、Gemini 在网关后按查询调度。 |
| [vLLM](/04-llmops/vllm/) 与 [SGLang](/04-llmops/sglang/) | 自研模型 serving 的社区栈；Perplexity 公开口径是与 NVIDIA 合作 TensorRT-LLM 并自写 kernel，同时关注这两条开源路线。 |

## 章节导航

1. [背景：为什么研究 Perplexity](01-background) — 创始团队与约 8 人早期公司、产品演进时间线、融资与规模（报道口径）、资料可信度三级约定。
2. [核心思想](02-core-ideas) — 推理经济学、速度即产品、模型无关主义三大支柱。
3. [架构设计](03-architecture) — 有出处的事实与明确标注的推断：AWS 全栈 + 检索栈 + 生成栈 + Agent 栈分层图。
4. [一次查询的生命线](04-workflow) — 查询理解→检索→重排→生成→引用的端到端流程与延迟预算。
5. [核心模块](05-core-modules) — Photon、CobbleDB、Sonar 模型族、缓存、SPACE、PerplexityBot 索引管线。
6. [生态与实现分析](06-source-analysis) — 开源盘点（r1-1776、SPACE、BrowseSafe 等）与四大案例的路线对比。
7. [Mini Demo](07-mini-demo) — 路由/缓存/流式/重排四个推理经济学权衡模型 + 5 个端到端场景（48 个测试）。
8. [企业生产实践](08-production-practice) — 版权诉讼战、出版商分成计划、模型供应商风险管理、多云多硬件布局。
9. [最佳实践](09-best-practices) — 可复用的推理经济学设计原则清单。
10. [面试题](10-interview-questions) — 初/中/高级 14 道题（带参考答案）。
11. [延伸阅读](11-further-reading) — 一手博客/文档、访谈、报道与手册内交叉引用。

## 一句话总结

Perplexity 证明了 AI 产品的护城河可以不是最强的模型，而是**最经济的推理**：用模型无关主义摆脱供应商锁定，用 tail latency 哲学把速度做成产品功能，用自建检索栈（爬虫 → Photon → CobbleDB）掌握答案的原材料，再把省下的每一分推理成本换成更快的产品迭代——代价是与出版行业的长期版权对峙，以及"搜索引擎是否被允许未经许可读取整个互联网"这个未决的法律问题。
