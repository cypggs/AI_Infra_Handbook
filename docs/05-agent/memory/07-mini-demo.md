# 7. 工程实践：Mini Agent Memory

> 一句话理解：**这个 Mini Demo 用纯 Python、零外部模型依赖实现一个最小可用的 Agent Memory 系统，展示工作记忆、短期记忆、长期语义记忆、情景记忆、向量检索、摘要压缩与多会话个性化**。

## Demo 设计

真实 Agent Memory 系统通常依赖外部 embedding 模型、向量数据库和持久化存储。为了在不依赖 GPU、不依赖外部 LLM key 的情况下讲清楚核心机制，本 Demo 采用纯 Python 实现：

- **Embedder**：使用确定性 hash-based 向量生成，无需下载模型。向量能体现 token 级别的相似性，足够教学。
- **Vector Store**：内存中存储 `(id, text, embedding, metadata)`，支持 cosine similarity 检索。
- **Retriever**：支持 vector、keyword、hybrid 三种检索模式。
- **Working Memory**：当前会话 messages 列表 + token 预算截断。
- **Short-term Memory**：最近 N 轮或滑动窗口摘要。
- **Long-term Semantic Memory**：基于 Vector Store 的用户偏好与事实。
- **Episodic Memory**：记录任务目标、关键动作、结果，用于后续经验复用。
- **Storage**：`InMemoryStorage` 与 `JsonFileStorage` 两种实现，演示持久化。
- **Memory Service**：统一 `remember(fact/session/task)` / `recall(query)` API。
- **Demo 脚本**：模拟多会话场景，展示 long-term memory 带来的个性化与 episodic memory 的经验复用。

## 目录结构

```text
docs/05-agent/memory/mini-demo/
├── README.md
├── pyproject.toml
├── agent_memory_mini/
│   ├── __init__.py
│   ├── working_memory.py      # 当前会话对话历史 / token 截断
│   ├── short_term_memory.py   # 滑动窗口 / 近期摘要
│   ├── long_term_memory.py    # 语义记忆：向量存储 + 检索
│   ├── episodic_memory.py     # 任务片段与成败记录
│   ├── procedural_memory.py   # 流程模板与工具使用经验
│   ├── embedder.py            # 确定性轻量 embedder（无外部模型依赖）
│   ├── vector_store.py        # 内存向量存储 + cosine 检索
│   ├── retriever.py           # vector / keyword / hybrid 检索
│   ├── summarizer.py          # 简单抽取式摘要
│   ├── storage.py             # 可插拔存储：memory / JSON file
│   ├── memory_service.py      # 统一 remember / recall 编排
│   └── demo.py                # 入口演示
└── tests/
    ├── __init__.py
    ├── test_working_memory.py
    ├── test_short_term_memory.py
    ├── test_long_term_memory.py
    ├── test_episodic_memory.py
    ├── test_embedder.py
    ├── test_vector_store.py
    ├── test_retriever.py
    └── test_memory_service.py
```

## 核心能力一览

| 能力 | 文件 | 说明 |
|---|---|---|
| 工作记忆 | `working_memory.py` | messages 列表 + token 截断策略 |
| 短期记忆 | `short_term_memory.py` | 滑动窗口与增量摘要 |
| 长期语义记忆 | `long_term_memory.py` | 基于向量存储的用户偏好与事实 |
| 情景记忆 | `episodic_memory.py` | 任务目标-动作-结果-反思四元组 |
| 程序性记忆 | `procedural_memory.py` | 流程模板与工具使用模式 |
| 向量编码 | `embedder.py` | hash-based deterministic embedder |
| 向量存储 | `vector_store.py` | 内存向量库 + cosine 相似度 |
| 检索器 | `retriever.py` | vector / keyword / hybrid |
| 摘要 | `summarizer.py` | 简单抽取式摘要与事实提取 |
| 可插拔存储 | `storage.py` | InMemoryStorage / JsonFileStorage |
| 统一服务 | `memory_service.py` | remember / recall / forget 编排 |
| 入口演示 | `demo.py` | 多会话个性化场景 |

## 快速运行

### 1. 安装依赖

```bash
cd docs/05-agent/memory/mini-demo
pip install -e ".[dev]"
```

### 2. 运行 Demo

```bash
python -m agent_memory_mini.demo
```

Demo 会模拟以下多会话场景：

1. **会话一**：用户告诉 Agent 自己喜欢 Python、不喜欢 Java。
2. **会话二**：用户要求推荐编程语言，Agent 通过 long-term semantic memory recall 出偏好，给出个性化回答。
3. **任务经验**：Agent 记录一次成功的推荐 episode，下次遇到类似任务时参考该经验。
4. **混合检索**：结合向量与关键词从长期记忆中检索相关事实。
5. **摘要压缩**：将较长的工作记忆压缩进短期记忆。

### 3. 运行测试

```bash
pytest tests/ -v
```

### 4. 作为库使用

```python
from agent_memory_mini.memory_service import MemoryService

service = MemoryService()

# 记住用户偏好
service.remember(
    memory_type="fact",
    content="用户 Alice 喜欢 Markdown 简洁周报",
    metadata={"user": "alice", "topic": "preference"},
)

# 检索相关记忆
results = service.recall("周报格式", memory_type="fact", top_k=3)
for r in results:
    print(r["text"])

# 持久化到磁盘
service.save("memory.json")

# 在新进程中恢复
new_service = MemoryService()
new_service.load("memory.json")
```

## 关键代码片段

### 确定性 Embedder

```python
from agent_memory_mini.embedder import DeterministicEmbedder

embedder = DeterministicEmbedder(dim=128)
vec = embedder.embed("我喜欢 Markdown 周报")
print(len(vec))  # 128
```

确定性 embedder 的好处是：

- 无需下载模型，CPU 可运行。
- 相同输入永远得到相同向量，便于测试与复现。
- 对教学场景足够展示“相似文本有相似向量”的效果。

局限性：

- 无法像真实 embedding 模型那样捕捉深层语义。
- 不同语言、同义词效果有限。
- 生产环境应替换为 sentence-transformers、OpenAI text-embedding-3 等真实模型。

### Memory Service 接口

```python
class MemoryService:
    def remember(
        self,
        memory_type: str,
        content: Any,
        metadata: Optional[dict] = None,
    ) -> str:
        """把信息写入指定类型的记忆。"""
        ...

    def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """从多层记忆中检索相关上下文。"""
        ...

    def forget(
        self,
        id_or_session_id: str,
        memory_type: Optional[str] = None,
    ) -> bool:
        """删除指定记忆。"""
        ...
```

### 多会话个性化场景

```text
[Session 1]
User: 我叫 Alice，我喜欢把周报写成 Markdown，内容要简洁。
Agent: 已记住你的偏好。

[Session 2]
User: 帮我写一份周报。
Agent（通过 semantic memory recall）:
    “Alice 喜欢 Markdown 简洁周报，我将使用 Markdown 格式并控制篇幅。”
```

## 测试结果示例

```text
tests/test_embedder.py::test_tokenize_handles_chinese_and_english PASSED
tests/test_embedder.py::test_embedding_is_deterministic_and_unit_norm PASSED
tests/test_embedder.py::test_similarity_ordering PASSED
tests/test_embedder.py::test_empty_text_embedding PASSED
tests/test_episodic_memory.py::test_store_and_recall_episodes PASSED
tests/test_episodic_memory.py::test_episode_contains_actions_and_outcome PASSED
tests/test_long_term_memory.py::test_remember_and_recall_facts PASSED
tests/test_long_term_memory.py::test_fact_id_increments PASSED
tests/test_memory_service.py::test_multi_session_recall PASSED
tests/test_memory_service.py::test_remember_task_and_example PASSED
tests/test_memory_service.py::test_forget_memory_and_session PASSED
tests/test_memory_service.py::test_save_and_load_json PASSED
tests/test_memory_service.py::test_consolidate_moves_working_to_short_term PASSED
tests/test_retriever.py::test_vector_retrieval PASSED
tests/test_retriever.py::test_keyword_retrieval PASSED
tests/test_retriever.py::test_hybrid_retrieval PASSED
tests/test_retriever.py::test_unknown_mode_raises PASSED
tests/test_short_term_memory.py::test_sliding_window_summarizes_old_turns PASSED
tests/test_short_term_memory.py::test_session_summary_storage PASSED
tests/test_short_term_memory.py::test_summarizer_prefers_frequent_words PASSED
tests/test_vector_store.py::test_add_search_ranking_and_delete PASSED
tests/test_working_memory.py::test_add_and_get_messages PASSED
tests/test_working_memory.py::test_clear_working_memory PASSED
tests/test_working_memory.py::test_truncate_preserves_system_messages PASSED
tests/test_working_memory.py::test_truncate_word_mode PASSED
tests/test_working_memory.py::test_invalid_budget_mode PASSED

============================== 26 passed in 0.04s ==============================
```

## 生产差异说明

| 能力 | Demo 实现 | 生产系统 |
|---|---|---|
| Embedder | Hash-based deterministic | sentence-transformers / OpenAI / Cohere |
| Vector Store | 内存 | Chroma / Weaviate / Milvus / pgvector |
| 存储 | 内存 / JSON 文件 | Postgres / Redis / 对象存储 |
| 摘要 | 简单抽取式 | LLM-based 生成式摘要 |
| 隐私过滤 | 教学版正则 | PII 检测模型 + 脱敏服务 |
| 多租户 | user_id 隔离 | namespace / collection / 物理隔离 |
| 可观测 | stdout | OpenTelemetry / Prometheus |

## 本章小结

Mini Demo 展示了一个零外部依赖、纯 Python 的 Agent Memory 系统：通过确定性 embedder、内存向量存储、可插拔 storage、多层记忆抽象与统一 Memory Service，实现了工作记忆、短期记忆、长期语义记忆、情景记忆、程序性记忆的存储与检索。虽然 embedder 和存储都是教学级实现，但已经覆盖了生产 Memory 系统的 80% 核心概念。推荐阅读 [`mini-demo/README.md`](./mini-demo/README.md) 获取完整运行说明，并在生产环境中替换为真实的 embedding 模型与向量数据库。

**参考来源**

- [Letta Documentation](https://docs.letta.com)
- [LangGraph Add Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
