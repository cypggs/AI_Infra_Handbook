# 核心概念

RAG 流水线可以抽象为一条“数据进、答案出”的管道。理解每个阶段的核心概念，是设计可扩展 RAG 系统的前提。

## 端到端 RAG 流水线

```text
原始文档 → 加载 → 分块 → 嵌入 → 向量索引 → （在线）

用户查询 → 查询理解 → 检索 → 重排 → 上下文组装 → 生成 → 后处理/引用
```

每个阶段都有明确的目标、可选算法和工程权衡。

## 1. 文档加载与解析（Document Loading）

- **Loader**：从 PDF、Word、网页、数据库、API 读取原始内容。
- **Parser**：把二进制文件解析为结构化文本，保留标题、表格、图片占位符。
- **关键问题**：扫描版 PDF 需要 OCR；表格需要保留行列关系；代码需要保留缩进与注释。

## 2. 分块（Chunking）

Chunk 是检索和生成的最小知识单元。分块策略直接影响召回率和生成质量。

| 策略 | 说明 | 适用 |
|---|---|---|
| 固定长度 | 按字符/Token 数切分 | 通用、简单 |
| 重叠滑动窗口 | 相邻 chunk 共享部分文本 | 避免上下文断裂 |
| 语义分块 | 按句子/段落语义边界切分 | 需要保留完整语义 |
| 结构分块 | 按标题、章节、Markdown 层级切分 | 技术文档、法律文本 |
| Agentic 分块 | 让模型决定切分边界 | 高精度、高成本 |

Chunk 过大：检索精度下降，生成上下文被浪费。  
Chunk 过小：语义不完整，生成缺乏上下文。  
**经验法则**：优先让 chunk 能独立回答一类问题，再调整长度。

2024–2025 年的两个重要改进：

- **Contextual Retrieval（上下文化检索）**：Anthropic 2024 年 9 月提出，在嵌入前先用 LLM 为每个 chunk 生成一段“文档级上下文说明”（例如“本 chunk 出自 Acme 2024 年报的退货政策章节”），再嵌入拼接后的文本。官方报告该方法把检索失败率从 5.7% 降到 2.9%，叠加 BM25 混合检索与重排后降到 1.9%（[Anthropic 工程博客](https://www.anthropic.com/news/contextual-retrieval)）。成本是每个 chunk 一次 LLM 调用，适合对检索质量敏感、可离线摊薄成本的场景。
- **Late Chunking（迟分块）**：Jina AI 2024 年提出（[arXiv:2409.04701](https://arxiv.org/abs/2409.04701)），把顺序反过来：先用长上下文 Embedding 模型（如 jina-embeddings-v3）读入整篇文档，再在其 token 级表示上做切分池化，让每个 chunk 的向量天然携带全文上下文，缓解“chunk 脱离语境后语义不完整”的经典问题。

## 3. 嵌入（Embedding）

Embedding 把文本映射为稠密向量，使得语义相似的文本在向量空间中距离近。

- **Dense Embedding**：BERT/Sentence-BERT、OpenAI `text-embedding-3`、BGE、E5 等。
- **Sparse Embedding**：BM25、SPLADE，基于词项统计，对关键词匹配友好。
- **Late Interaction**：ColBERT 在查询时保留 token 级交互，精度高但计算重；2025 年后已有多向量张量索引与专用 Reranker 让这条路线进入生产（见多模态 RAG 一节）。
- **多模态 Embedding**：CLIP、图像编码器，把图片、表格也映射到同一向量空间。

**2025 年的新基线**：Qwen3-Embedding 系列（[arXiv:2506.05176](https://arxiv.org/abs/2506.05176)）提供 0.6B/4B/8B 三档、32K 上下文、100+ 语言，8B 版本在 2025 年 6 月登顶 MTEB 多语言排行榜（70.58 分），并支持 MRL（Matryoshka）可变维度出码；配套的 Qwen3-Reranker 用“是/否”token 打分（生成式评分），效果与商用 API 相当。开源 Embedding 的选型如今基本围绕 **MTEB/MTEB-Chinese 排行榜**展开，中文场景重点关注 BGE-M3、GTE-Qwen 与 Qwen3 系列。

## 4. 向量存储与索引（Vector Store & Index）

向量库负责高效存储和近似最近邻（ANN）检索。

| 能力 | 说明 |
|---|---|
| ANN 索引 | HNSW、IVF、DiskANN 等，用精度换速度 |
| 元数据过滤 | 在向量检索前按 source、tenant、date 过滤 |
| 混合检索 | 同时保留向量索引与倒排索引 |
| 增量更新 | 支持 upsert、delete、versioning |

常见向量库：Milvus、Pinecone、Weaviate、Qdrant、Chroma、pgvector、Faiss、Elasticsearch。

## 5. 检索策略（Retrieval）

| 策略 | 原理 | 优点 | 缺点 |
|---|---|---|---|
| Dense Retrieval | 向量相似度 | 语义泛化好 | 对罕见词、专有名词弱 |
| Keyword/Sparse Retrieval | BM25/TF-IDF | 精确匹配、可解释 | 语义鸿沟 |
| Hybrid Retrieval | 稠密+稀疏融合 | 兼顾语义与关键词 | 需要调权与融合算法 |
| RRF | Reciprocal Rank Fusion | 无需归一化，鲁棒 | 仅利用排名，丢失绝对分值 |
| Multi-Query | 一个查询扩展为多个子查询 | 提高召回 | 增加检索成本 |
| Query Rewriting | 用 LLM 改写/扩展查询 | 弥合查询与文档语义 gap | 增加延迟与 token 成本 |
| Agentic Retrieval | 模型自主决定检索时机、查询与迭代 | 多跳问题显著提升 | 延迟与成本数倍增长，需要预算控制 |

到 2025 年，**“BM25 + Dense 混合检索 + RRF 融合”已成为生产 RAG 的事实标配**，行业报告显示多数企业级 RAG 都走这一路线；纯 dense 检索只在语料简单、专有名词少的场景单独使用。更复杂的查询则交给 **Agentic 检索范式**：Router Agent 先判断查询类型（单跳/多跳/比较/闲聊），Iterative Agent 则在推理过程中循环“检索 → 反思 → 改写再检索”，有行业评测显示，多跳问答准确率相比单次 RAG 可从三成多提升到近八成，但 token 成本约 3 倍、延迟约 4 倍——评测与路由时应以**“每个正确答案的成本”（cost per correct answer）**而非单次延迟为指标（[Agentic RAG 综述](https://arxiv.org/abs/2501.09136)）。

## 6. 重排（Reranking）

检索阶段追求高召回，重排阶段追求高精度。

- **Cross-Encoder**：把 query 与 chunk 拼接后输入模型打分，精度高但延迟大。
- **Listwise / 生成式 Reranker**：2025 年的新趋势，如 Qwen3-Reranker 用“是/否”token 做生成式打分，Cohere Rerank 3.5、Voyage rerank-2.5 等商用 API 与开源模型（BGE-reranker-v2-m3）形成互补；Listwise 方案一次给整个候选列表打分，对头部排序更稳定。
- **Bi-Encoder + 轻量模型**：先用双塔召回，再用小模型重排。
- **特征融合**：结合向量分数、关键词分数、元数据 freshness、用户反馈。
- **多向量 Reranker**：ColBERT 式 late interaction 重排（含 ColPali 系视觉 Reranker），token 级交互精度最高，但推理开销大，通常用于高价值候选的精排。

Reranker 通常只处理 Top-K（如 50→20 或 20→5），控制成本。

## 7. 生成增强（Generation Augmentation）

把检索到的 chunks 注入 prompt，常见模式：

```text
根据以下参考资料回答问题：
---
[1] {chunk1}
[2] {chunk2}
---
问题：{query}
要求：仅使用参考资料，并标注引用编号。
```

生成阶段的关键：

- **上下文排序**：最相关的 chunk 放在 prompt 前后两端（中间位置易丢失）。
- **引用生成**：让模型输出 `[1]`、`[2]` 等引用标记。
- **后处理**：验证引用是否真实存在，防止幻觉引用。
- **拒绝回答**：当检索结果置信度低时，让模型回答“不知道”。

## 8. 多模态 RAG（Multimodal RAG）

真实企业文档大量是版式复杂的 PDF：表格、图表、印章、手写批注。传统方案依赖 OCR 与版式解析，流水线脆弱且丢失视觉信息。2025 年的标志性进展是 **ColPali**（[arXiv:2407.01449](https://arxiv.org/abs/2407.01449)，ICLR 2025）：

- 不再解析 PDF，而是把每页渲染成图片，用视觉语言模型（PaliGemma-3B）直接编码为**多向量表示**（每页多个 patch embedding）。
- 检索时用 ColBERT 式 late interaction（MaxSim）打分，在 ViDoRe 基准上大幅超越文本解析路线。
- 衍生出 ColQwen2、ColSmolVLM 等变体；2026 年初 Qwen3-VL Embedding（2B）进一步把该路线带入 Qwen 生态。

工程代价是**索引与存储成本高**（每页几十上百个向量），以及 late interaction 需要张量级检索引擎或候选剪枝（先用单向量粗召回，再做多向量精排/重排）。

## 9. 评估（Evaluation）

| 维度 | 指标 | 含义 |
|---|---|---|
| 检索质量 | Hit Rate、MRR、NDCG@K、Recall@K | 相关文档是否被召回、排名是否靠前 |
| 生成质量 | Faithfulness、Answer Relevance | 答案是否忠实于检索内容、是否回答用户问题 |
| 端到端 | RAGAS、ARES、TruLens | 综合评估检索+生成 |
| 鲁棒性 | RGB（噪声/拒答/反事实）、RAGTruth（幻觉） | 系统面对脏数据与对抗输入的表现 |
| 场景覆盖 | CRUD-RAG（增删改查）、RAGBench（行业 TRACe 框架） | 超越纯 QA 的真实任务形态 |
| 效率 | 检索延迟 P99、吞吐、索引构建时间、每次正确答案成本 | 系统性能与经济性 |

两个 2025 年后的评估趋势：

1. **检索与生成分层归因**：RAGBench/BERGEN 等基准强调把端到端错误归因到“检索没召回”还是“生成没用好”，分别优化；实践结论是检索质量对最终效果的预测力最强——重排与混合检索的收益首先体现在检索指标上。
2. **Agentic RAG 的评估对象变了**：评估单元从“单次 query-answer”变成“多步轨迹”（检索次数、查询质量、反思是否有效、是否过早停止），并引入成本指标（token、延迟、每次正确答案成本）。

## 小结

RAG 不是“向量库 + LLM”的简单拼接，而是一个需要反复权衡的流水线：chunk 多大、embedding 多强、检索多深、重排多准、生成多可控。下一章将从架构视角把这些概念组织成可落地的系统。
