# Mini Demo

本章介绍 `docs/06-rag/mini-demo/` 中的 RAG 迷你示例。它用纯 Python 标准库实现了一个完整的 RAG 流水线，无需 GPU、无需外部 API key，方便你直接运行、调试与扩展。

## 场景

示例围绕虚构的 **Acme Corp** 文档：

- 公司历史
- 产品介绍
- 退货政策
- 保修政策

用户提问：“What is Acme Corp's return policy?” 系统会检索相关 chunk，重排后给出带引用的答案。

## 目录结构

```text
mini-demo/
├── pyproject.toml
├── README.md
├── rag_mini/
│   ├── __init__.py
│   ├── documents.py      # 样本文档与重叠分块
│   ├── embedder.py       # TF-IDF 确定性嵌入
│   ├── vector_store.py   # 内存向量库 + 元数据过滤
│   ├── retriever.py      # Dense / Keyword / Hybrid(RRF)
│   ├── reranker.py       # 简单分数融合重排
│   ├── generator.py      # Mock LLM：基于检索上下文生成答案
│   └── demo.py           # run_demo() 入口
└── tests/
    ├── __init__.py
    ├── test_documents.py
    ├── test_embedder.py
    ├── test_vector_store.py
    ├── test_retriever.py
    ├── test_reranker.py
    ├── test_generator.py
    └── test_demo.py
```

## 安装与运行

```bash
cd docs/06-rag/mini-demo
pip install -e ".[dev]"

# 运行 demo
python -m rag_mini.demo

# 或安装后使用脚本
rag-demo
```

## 运行示例

```text
Question: What is Acme Corp's return policy?

Retrieved chunks:
  1. [returns] Acme Corp accepts returns within thirty days of purchase ...
  2. [products] Acme Corp offers a wide range of products ...
  3. [company-history] Acme Corp was founded in 1985 ...

Answer: Acme Corp accepts returns within thirty days of purchase with the
original receipt. Items must be unused and in original packaging, and refunds
are processed within five to seven business days.
```

## 关键代码片段

### 1. 分块

```python
from rag_mini.documents import load_chunks

chunks = load_chunks(chunk_size=40, overlap=10)
for chunk in chunks:
    print(chunk.id, chunk.section, chunk.text[:60])
```

### 2. 嵌入与向量存储

```python
from rag_mini.embedder import Embedder
from rag_mini.vector_store import VectorStore

embedder = Embedder(chunks)
store = VectorStore(embedder.get_embedded_chunks())

query_vector = embedder.embed_query("return policy")
results = store.similarity_search(query_vector, top_k=3)
```

### 3. 混合检索（Dense + Keyword + RRF）

```python
from rag_mini.retriever import Retriever

retriever = Retriever(embedder=embedder, vector_store=store)
candidates = retriever.hybrid_search("return policy", top_k=5)
```

### 4. 重排

```python
from rag_mini.reranker import Reranker

reranker = Reranker()
ranked = reranker.rerank("return policy", candidates)
```

### 5. 生成

```python
from rag_mini.generator import Generator

generator = Generator()
context = [r.chunk for r in ranked]
answer = generator.generate("What is the return policy?", context)
print(answer.text)
```

## 测试

```bash
pytest tests/ -q
```

当前测试覆盖：

- 分块边界与重叠逻辑
- 嵌入器确定性与向量维度
- 向量存储的相似度搜索与元数据过滤
- Dense / Keyword / Hybrid 检索
- Reranker 排序与分数范围
- Generator 答案匹配与空上下文兜底
- Demo 端到端输出

## 与生产系统的差异

| 方面 | Mini Demo | 生产系统 |
|---|---|---|
| Embedding | TF-IDF（无模型） | 神经网络 embedding 服务 |
| 向量存储 | 内存列表 | Milvus/Pinecone/Qdrant 等 |
| 检索 | 暴力相似度 + BM25 | ANN + 分布式倒排索引 |
| Reranker | 分数融合 | Cross-Encoder / 学习排序 |
| Generator | Mock LLM | GPT-4 / Claude / 自研模型 |
| 可观测 | 无 | Trace、Metrics、Eval |
| 多租户/权限 | 无 | namespace / ACL / 审计 |

## 扩展练习

1. 把 `Embedder` 换成真实的 sentence-transformers 模型。
2. 把 `VectorStore` 替换为 Chroma 或 Qdrant，观察大规模下的延迟。
3. 在 `Retriever` 中加入查询改写（query rewriting）模块。
4. 给 `Generator` 接入真实的 LLM API，并增加引用校验。
5. 用 RAGAS 评估这个 demo 的 faithfulness 与 answer relevance。

## 小结

Mini Demo 虽小，但完整展示了 RAG 的五个核心阶段：**加载与分块、嵌入、检索、重排、生成**。它是理解后续生产实践章节的基础沙盒。
