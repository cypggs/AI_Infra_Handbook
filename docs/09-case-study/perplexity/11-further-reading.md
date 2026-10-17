# 11. 延伸阅读

## 一手来源（官方博客 / 文档 / 公告）

### Perplexity 官方工程博客（perplexity.ai/hub/blog，2026 年密集披露）

- **Photon: Building a retrieval and ranking engine from scratch**（2026-09-24）——检索/排序引擎完整设计：broker/shard 架构、WAND 式遍历、Elias-Fano 编码、io_uring 异步读、CLOCK 缓存、构建/查询分离、滚动发布；p99 800→65 ms、省 20% 机器、每文档 2.5 倍数据、Fast Search 160 ms p50 / 230 ms p95。本主题 [5.1](05-core-modules) 的主来源。
- **CobbleDB 发布博客**（2026-09-14）——Rust/RocksDB 热 KV 存储替换 DynamoDB：Pillar/Lorry/CobbleDB 三级、hedged reads、可用区亲和；batch read 31.4→5.6 ms；2 名工程师 + AI 代理 2 个月建成。主来源 [5.2](05-core-modules)。
- **Open-sourcing SPACE, the sandbox platform behind Computer**（2026-10-15）——VM 级隔离沙箱开源：每天数百万创建、创建快 3–5 倍、108 次逃逸对抗全失败、部署伙伴 Akamai/Crusoe/CoreWeave。主来源 [5.5](05-core-modules)。
- **How we engineer safer agents**（2026-09-29）——Agent 安全工程综述，提及 BrowseSafe / Numbat / Bumblebee 等已开源工具。
- **Multimodal embeddings beyond a single vector**（2026-10-07）——embedding 研究，配合官方 Embeddings API（标准 + 上下文感知两种）。

### 官方文档（docs.perplexity.ai）

- **定价页**——Sonar 系定价（sonar $1/$1、sonar-pro $3/$15、sonar-reasoning-pro $2/$8 每百万 token + 按上下文档位的请求费；Deep Research 按 citation/reasoning token 与搜索次数计费）。本主题 [5.3](05-core-modules) 引用。
- **Sonar → Agent API 迁移指南与基准**——Sonar API 2026-09-27 退役；BrowseComp/DSQA 上各 Sonar 档位与 Agent presets 的得分/成本对比（fast 预设 64.3% @ $59.73 vs 默认 64.0% @ $187.60）。
- **Agent API / Orchestrator / Search / Embeddings / Decisions 文档**——model fallback、presets、工具集（web search、MCP、连接器）、后台模式等。

### 合作伙伴一手公告

- **Cerebras: Powers Perplexity Sonar with Industry's Fastest AI Inference**（2025-02-11）——Sonar（Llama 3.3 70B 基座）在 CS-3 上约 1200 token/s，Pro 用户可用；CTO Denis Yarats 引语。本主题 [5.3](05-core-modules) 引用。
- **Crusoe × Perplexity 多年期合作公告**——GB300 NVL72 + InfiniBand 生产级推理；Aravind "at Perplexity scale every millisecond of latency is felt by users"。
- **AWS 案例材料**（awsstatic.com 的 Perplexity PDF）——SageMaker HyperPod、Bedrock 多模型接入、Trainium 试验；注意营销口径。
- **r1-1776**——Hugging Face `perplexity-ai/r1-1776` 模型卡与发布说明（2025-02-18）：DeepSeek-R1 671B 后训练、约 4 万条多语言数据、NeMo 2.0、MIT 许可。

## 访谈（一手转述，注意受访者立场）

- **Lex Fridman Podcast #434：Aravind Srinivas**（lexfridman.com/aravind-srinivas-transcript）——本主题引用最多的单源：tail latency 哲学（每层 P90/P99）、TTFT/吞吐两指标、"自推理更快"、TensorRT-LLM 与自写 kernel、全栈 AWS、"我们不在乎模型权重"、Sonar = Llama 3 后训练、混合排序信号（BM25 + 向量 + 域名权威 + 时效）、自建 PerplexityBot、Google 300–400 ms 对照、飞机 Wi-Fi 测试。
- Aravind 的其他长访谈（如 a16z、Sequoia、YC 系播客）——"2023 年初约 8 人团队"、早期用 Bing 索引 API 后转自建、月查询量 7.8 亿（2025-05）等口径的来源。

## 报道（二手，注意口径差异）

- **融资与估值**：TechCrunch（2024-12-19，5 亿美元 @ 90 亿美元交割确认）；2025 年 Accel 轮（约 140 亿）与 2025-09 轮（200 亿）、2026 年 NVIDIA 洽谈（300 亿+，未证实）见 Reuters / FT / The Information 系列报道。
- **收入**：FT（2026-03，年化约 4.5 亿美元）、Reuters / The Information（2026-08，超 7.5 亿美元）。
- **版权对峙**：Wired《Perplexity Is a Bullshit Machine》（2024-06-19，爬虫绕过 robots.txt 调查）；Forbes 公开指责（2024-06）；Reuters 对 NYT cease-and-desist、BBC 威胁起诉的系列报道；Dow Jones / NYT / Britannica 诉讼文书（2025）。
- **Amazon 诉讼**：2025-11 对 Comet Agent 访问用户账户的指控及后续上诉程序（法院文书与报道）。
- **Cerebras × Sonar 报道**：VentureBeat（2025-02）——补充 factual accuracy 85.1 vs GPT-4o 83.9 的对比口径。

## 第三方技术拆解（参考性质）

- 各技术媒体对 Photon / CobbleDB 的解读（如 The New Stack 对 "AI agents helped build a database" 的访谈）——注意其简化与推测成分。
- 学术侧参照：Open Deep Search（arXiv:2503.20201）将 Sonar Reasoning Pro / GPT-4o Search Preview 列为专有搜索 AI 基线。

## 手册内交叉引用

### 案例研究互参

- [OpenAI 案例研究](/09-case-study/openai/)——供应商兼竞争者的对照样本；ChatGPT Search 的竞争分析。
- [Google 案例研究](/09-case-study/google/)——AI Overviews/Gemini 的"搜索巨头 AI 化"路线对照；TPU 垂直整合 vs Perplexity 的拿来主义。
- [DeepSeek 案例研究](/09-case-study/deepseek/)——推理经济学另一极（训练侧效率）；r1-1776 的基座来源；推理利润率模型对照。
- [xAI 案例研究](/09-case-study/xai/)——零训练 vs 百万卡训练的对照；Grok 作为接入模型之一。
- [Cursor 案例研究](/09-case-study/cursor/)——同为"不拥有基础模型"阵营：模型阶梯、在线 RL 与订阅制推理经济学的另一份样本。
- [Anthropic 案例研究](/09-case-study/anthropic/)——Claude 供应商关系与模型安全文化的对照。

### 技术主题深挖

- [RAG](/06-rag/)——检索、重排、引用纪律的产品化实现；缓存与新鲜度矛盾。
- [向量数据库与 Embedding 基础设施](/06-rag/vector-db/)——CobbleDB 说明 AI 搜索存储 ≠ 向量库；倒排 + KV + 对象存储的分层。
- [LLM Gateway](/04-llmops/llm-gateway/)——模型无关主义的网关机制：路由、fallback、计费。
- [vLLM](/04-llmops/vllm/) 与 [SGLang](/04-llmops/sglang/)——自研模型 serving 的社区栈，对照 TensorRT-LLM 路线。
- [Kubernetes](/02-cloud-native/kubernetes/)——全托管云底座（AWS）上的容器编排语境。
- [计算机网络](/01-foundation/computer-networks/)——Cerebras 晶圆级互联与 Crusoe GB300 NVL72 + InfiniBand 的网络视角。
