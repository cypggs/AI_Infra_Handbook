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

## 3. 嵌入（Embedding）

Embedding 把文本映射为稠密向量，使得语义相似的文本在向量空间中距离近。

- **Dense Embedding**：BERT/Sentence-BERT、OpenAI `text-embedding-3`、BGE、E5 等。
- **Sparse Embedding**：BM25、SPLADE，基于词项统计，对关键词匹配友好。
- **Late Interaction**：ColBERT 在查询时保留 token 级交互，精度高但计算重。
- **多模态 Embedding**：CLIP、图像编码器，把图片、表格也映射到同一向量空间。

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

## 6. 重排（Reranking）

检索阶段追求高召回，重排阶段追求高精度。

- **Cross-Encoder**：把 query 与 chunk 拼接后输入模型打分，精度高但延迟大。
- **Bi-Encoder + 轻量模型**：先用双塔召回，再用小模型重排。
- **特征融合**：结合向量分数、关键词分数、元数据 freshness、用户反馈。

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

## 8. 评估（Evaluation）

| 维度 | 指标 | 含义 |
|---|---|---|
| 检索质量 | Hit Rate、MRR、NDCG@K | 相关文档是否被召回、排名是否靠前 |
| 生成质量 | Faithfulness、Answer Relevance | 答案是否忠实于检索内容、是否回答用户问题 |
| 端到端 | RAGAS、ARES、TruLens | 综合评估检索+生成 |
| 效率 | 检索延迟 P99、吞吐、索引构建时间 | 系统性能 |

## 小结

RAG 不是“向量库 + LLM”的简单拼接，而是一个需要反复权衡的流水线：chunk 多大、embedding 多强、检索多深、重排多准、生成多可控。下一章将从架构视角把这些概念组织成可落地的系统。
