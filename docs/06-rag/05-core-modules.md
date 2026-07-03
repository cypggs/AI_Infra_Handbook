# 核心模块

把 RAG 流水线拆成独立模块后，每个模块都有清晰的接口、实现选项和工程权衡。下面按数据流顺序逐一说明。

## 1. Document Loader

**职责**：从多种来源读取原始文档并附带元数据。

- 来源：S3、GCS、OSS、SharePoint、Confluence、数据库、Git、API。
- 输出：`(raw_bytes, mime_type, source_url, updated_at, owner, acl)`。
- 关键点：增量加载依赖 source 的 change feed 或 last_modified 时间戳。

## 2. Document Parser

**职责**：把二进制文件解析为结构化文本。

- PDF：文本提取（PyPDF/pdfplumber）或 OCR（Tesseract/PaddleOCR）。
- Office：python-docx、python-pptx。
- HTML/Markdown：保留标题层级、表格、代码块。
- 代码：保留文件路径、注释、函数签名。

**输出结构示例**：

```json
{
  "title": "退货政策",
  "sections": [
    {"heading": "退货期限", "text": "...", "level": 2},
    {"heading": "退款方式", "text": "...", "level": 2}
  ],
  "tables": [...]
}
```

## 3. Chunker

**职责**：把文档切分为语义完整的 chunk。

- 接口：`chunk(document) -> list[Chunk]`。
- 元数据：source、section、heading、page、position、tenant_id。
- 实现：固定长度、重叠窗口、Markdown 结构、语义分块、Agentic 分块。

**关键权衡**：

| 粒度 | 检索精度 | 语义完整 | token 效率 |
|---|---|---|---|
| 小 chunk（128 tokens） | 高 | 低 | 低 |
| 中 chunk（512 tokens） | 中 | 中 | 中 |
| 大 chunk（2048 tokens） | 低 | 高 | 高 |

## 4. Embedder

**职责**：把 chunk/query 编码为向量。

- 接口：`embed(texts: list[str]) -> list[list[float]]`。
- 模型选择：
  - 通用：OpenAI `text-embedding-3-small/large`、BGE、E5。
  - 多语言：BGE-M3、E5-mistral。
  - 代码：code-embedding 模型。
- 工程：批量、异步、缓存、失败重试、模型版本管理。

## 5. Vector Store

**职责**：存储向量与 metadata，支持 ANN 检索与过滤。

- 接口：`upsert(chunks)`、`search(query_vector, top_k, filters)`、`delete(ids)`。
- 关键能力：
  - ANN 索引（HNSW、IVF_PQ、DiskANN）。
  - Metadata 过滤（前置过滤、后置过滤）。
  - 混合索引（向量 + 倒排）。
  - 多租户（namespace/collection）。

## 6. Retriever

**职责**：根据 query 召回候选 chunks。

- Dense Retriever：`query_vector · chunk_vector`。
- Keyword Retriever：BM25 / TF-IDF。
- Hybrid Retriever：融合 dense 与 sparse 排名（RRF 或线性加权）。
- Multi-Query Retriever：把 query 扩展成多个子查询分别检索后合并。

## 7. Reranker

**职责**：在召回候选中筛选最相关的 chunk。

- Cross-Encoder：高精度、高延迟，适合 Top-100 → Top-10。
- 轻量模型：如 BGE-Reranker、MiniLM，适合在线。
- 特征融合：结合向量分、关键词分、freshness、点击率。

## 8. Query Engine

**职责**：编排查询生命周期。

- 接口：`answer(query, context) -> Answer`。
- 内部：preprocess → retrieve → rerank → assemble → generate → post-process。
- 支持配置：是否启用 rerank、最大检索数量、超时、fallback。

## 9. Generator Client

**职责**：调用 LLM 生成答案。

- 通过 LLM Gateway 统一路由。
- Prompt 模板管理（版本化、A/B 测试）。
- 输出解析：提取答案、引用、置信度。

## 10. Memory / Cache

**职责**：加速重复查询与重复检索。

- Query Cache：相同 query 直接返回缓存答案。
- Embedding Cache：避免重复编码相同 query/chunk。
- Retrieval Cache：缓存热门检索结果。
- Conversation Memory：多轮对话上下文管理。

## 11. Evaluator

**职责**：离线/在线评估 RAG 效果。

- 检索指标：Hit Rate、MRR、Recall@K、NDCG@K。
- 生成指标：Faithfulness、Answer Relevance、Context Precision、Context Recall。
- 框架：RAGAS、ARES、TruLens、LangSmith。

## 12. Observer

**职责**：全链路可观测。

- Trace：query → rewrite → retrieval → rerank → generation → answer。
- Metrics：latency P50/P99、retrieval latency、token cost、cache hit rate。
- Logging：记录 prompts、retrieved chunks、模型输出（注意 PII 脱敏）。

## 小结

这些模块并非每个系统都需要独立部署。小规模场景可以把多个模块合并在一个服务里；大规模场景则会把 Embedder、Vector Store、Retriever、Reranker、Generator 拆成独立可扩展的微服务。下一章会结合开源生态，看这些模块在主流框架中是如何实现的。
