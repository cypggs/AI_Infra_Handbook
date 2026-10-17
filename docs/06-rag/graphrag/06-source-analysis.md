# 生态与源码分析：GraphRAG / LightRAG / HippoRAG / KAG 对比

本章做两件事：给出主流图检索实现的横向对比（截至 2026-10），并对代表性设计做源码/论文级的概念解读。

## 6.1 主流实现对比

| 维度 | GraphRAG（微软） | LightRAG（HKU） | HippoRAG 2（OSU） | nano-graphrag | KAG（蚂蚁/OpenSPG） |
|---|---|---|---|---|---|
| 论文 | arXiv 2404.16130 | arXiv 2410.05779（EMNLP 2025 Findings） | arXiv 2502.14802（ICML 2025） | 无（实现项目） | arXiv 2409.13731 |
| 索引范式 | KG + 社区摘要 | KG + 向量双索引 | KG + PPR（无摘要） | 简版 GraphRAG | Schema KG + 逻辑形式 |
| 查询模式 | local / global / DRIFT / basic / 问题生成 | local / global / hybrid / naive / mix（5 种） | PPR 多跳检索 | naive + global（top-K 中心社区） | 规划-推理-检索三段式 |
| 全局能力 | 强（社区报告，LazyGraphRAG 可延迟） | 弱（global 模式仅基于实体/关系描述聚合） | 弱 | 中（中心社区摘要） | 强（逻辑推理） |
| 增量更新 | 批式重跑 | 一等公民（增量插入 + 2025.08 起删除重建子图） | 持续并入（持续学习定位） | 支持增量插入 | 批式为主 |
| 存储后端 | 文件/Parquet/Cosmos DB/SQLite + 可配向量库 | 默认 JSON（小数据）；推荐 PostgreSQL，支持 MongoDB/OpenSearch/Neo4j/Memgraph/Milvus/Qdrant | Neo4j/Ray 版 + FAISS | NetworkX/Neo4j + nano-vectordb/hnswlib | OpenSPG 引擎 |
| 抽取 | LLM（含 gleaning），prompt 可自动调优 | LLM，四角色独立配置（EXTRACT/QUERY/KEYWORDS/VLM） | LLM OpenIE + 在线过滤（v2） | LLM（单轮） | Schema 约束抽取 + 概念对齐 |
| 生产化 | CLI 完整；维护模式（只修 bug/安全，不加新功能） | Server + WebUI、RAGAS、Langfuse、多模态 RAG-Anything | 研究代码为主 | 教学/二开友好 | 领域方案（法务/医疗/政务） |
| 许可 / 热度 | MIT，约 36k stars | MIT，约 40k stars | 研究开源 | MIT，约 4k stars | Apache-2.0，约 9k stars |

选型速查：

- **全局概览是刚需、语料相对稳定**：GraphRAG（或其 LazyGraphRAG 思路改造）。
- **更新频繁、QPS 敏感、团队工程资源有限**：LightRAG（生产化最快，2025-2026 的迭代重心全在存储/评估/可观测性上）。
- **多跳问答是核心场景**（知识库问答、科研助手）：HippoRAG 2 路线（PPR + passage 融合），或在 LightRAG 上自实现 PPR。
- **想读懂原理、二次开发**：nano-graphrag（约 1100 行核心代码），读完它再读 GraphRAG 事半功倍。
- **强专业域、有本体工程能力**：KAG（schema 约束 + 逻辑形式推理在垂直域的收益远大于通用域）。

## 6.2 GraphRAG 源码级解读：verb 化流水线

微软 graphrag（v3.x，2026-10 最新 v3.3.0）的索引实现是一个 **verb 数据变换管线**：每个 verb 是纯函数式的表变换（pandas DataFrame 风格），用 config 的 workflow 定义串起来：

```text
文档 → create_text_units → create_base_extracted_entities（LLM 抽取 + gleaning）
     → create_base_entity_graph（合并 + 图嵌入）→ create_final_entities / relationships
     → create_base_community_reports（Leiden + map-reduce 报告）
     → create_final_community_reports / nodes / text_units → sink 到存储
```

三个值得学的工程决策：

1. **一切中间产物是表**：实体表、关系表、社区表、报告表，全部可 dump 成 Parquet 检查。调试 GraphRAG 的第一步永远是打开这些表看数据，而不是猜 prompt。
2. **缓存到 verb 级**：每个 verb 的输出带 content hash，重跑时只重算变化的 verb。2025 年的 v3.2.0 重做了缓存实现，进一步降低迭代调优成本。
3. **LLM 全部走 LiteLLM 代理**：模型供应商无关（OpenAI/Azure/本地 vLLM 均可），2025 年安全事件后官方固定了 LiteLLM 版本——依赖供应链安全在 LLM 中间件上同样成立。

维护模式信号：官方 README 明示进入维护状态（继续修 bug 和安全问题，不接受新 feature）。选型时应把它当作"稳定的参考实现"，期待社区（LightRAG 等）承担演进。

## 6.3 LightRAG 源码级解读：双层检索的数据流

LightRAG 的核心数据结构只有三张表：**实体表**（name → {type, description, embedding}）、**关系表**（(src,dst) → {keywords, description, weight, embedding}）、**chunk 表**。检索时：

```text
问题 → 关键词展开（LLM 抽出高低两层关键词）
     → 低层：关键词向量检索 命中实体 → 取实体 description + 一跳关系
     → 高层：关键词向量检索 命中关系 → 取关系 description 与两端实体
     → 合并去重 → 与 naive 向量检索结果融合 → 上下文
```

低层找"点"、高层找"边"的设计，让它不依赖社区结构也能给出结构化上下文；而实体/关系都带 embedding 意味着**图本身可以用向量库实现**（其 PostgreSQL 后端就是 PG 表 + pgvector 列）。2026 年的版本进一步把 chunking 策略（Fix/Recursive/Vector/Paragraph）与 LLM 角色（EXTRACT/QUERY/KEYWORDS/VLM 独立配置）做成可插拔项——工程上这是"把 LLM 调用面收拢成少数几个角色函数"的好范式。

## 6.4 HippoRAG 源码级解读：PPR 与 passage 融合

HippoRAG 的检索实现分三段：

1. **查询侧 OpenIE**：对问题抽三元组，把问题实体链接到 KG 节点（与索引侧同一套抽取器，保证分布一致）；
2. **PPR 传播**：从种子节点跑 Personalized PageRank（v2 引入节点加权与两遍传播：先 dense retrieval 出候选节点集，再在诱导子图上跑 PPR，控制计算量）；
3. **passage 融合排序**：节点得分 → 关联 passage 得分（节点得分求和 + passage 自身向量得分），联合排序取 top-k。

HippoRAG 2（ICML 2025）的进化在两头：索引侧"更深的 passage 整合"（ OpenIE 与 passage 的双向链接更密），查询侧"更有效的在线 LLM 使用"（用 LLM 对检索到的三元组做过滤打分，而非直接当上下文）。官方报告在关联记忆类任务上相对强 embedding 检索有约 7 个点的 F1 提升。

## 6.5 我们的 Mini Demo 与真实实现的差距

`graphrag_mini` 是有意简化的教学模型，与真实系统的差距清单：

| 方面 | Mini Demo | 真实系统 |
|---|---|---|
| 抽取 | 词典 + 模板规则 | LLM OpenIE + gleaning；schema-free vs schema 约束 |
| 谓词 | 14 个模板谓词 + RELATED_TO 回退 | 开放式谓词空间 + 归一化层 |
| 实体解析 | 词典天然消歧（同名词条唯一） | 名称/描述相似度归并 + 人工队列 |
| 社区检测 | 异步标签传播（确定性，2 层） | Leiden（随机性需固定种子），多分辨率多层 |
| 社区摘要 | 频次统计聚合文本 | LLM map-reduce，字数预算，来源回链 |
| 向量基线 | 字符 n-gram 哈希 + 暴力余弦 | BGE/Qwen3-Embedding + HNSW（见[向量数据库主题](/06-rag/vector-db/)） |
| 多跳 | BFS 全路径（小图可行） | PPR / beam search（大图必须近似） |
| 存储 | 进程内邻接表 | Neo4j/NebulaGraph/PG + 向量库 |
| 成本 | 调用次数计数 | token 计费 + 缓存 + 预算控制 |

保留不变的核心直觉：**索引是把语料预消化成"实体关系图 + 分层摘要"，查询是按问题类型在图上选择遍历策略**——理解了 Mini Demo 的数据流，真实系统的文档与源码都会变得好读。

## 小结

- 选型一句话：全局概览找 GraphRAG、工程生产找 LightRAG、多跳问答找 HippoRAG、读懂原理找 nano-graphrag、垂直深域找 KAG。
- GraphRAG 的 verb 化流水线与表化中间产物、LightRAG 的角色化 LLM 配置、HippoRAG 的 PPR+passage 融合，是三个最值得抄的工程范式。
- 微软 GraphRAG 进入维护模式，2025-2026 的创新重心已实质转移到 LightRAG 等社区实现。
