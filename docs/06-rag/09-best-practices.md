# 最佳实践

RAG 系统的效果往往取决于大量细节。本章整理了一份可直接落地的检查清单和常见反模式。

## Chunking 检查清单

- [ ] Chunk 能独立回答一类常见问题，不依赖上下文补全。
- [ ] 相邻 chunk 保留适当重叠（通常 10%~20%），避免语义断裂。
- [ ] 对结构化文档优先按标题/章节切分，而不是纯按长度。
- [ ] 保留 metadata（source、section、page、updated_at）。
- [ ] 对表格、代码等特殊内容使用专用切分策略。
- [ ] 预算允许时为 chunk 注入文档级上下文：优先评估内生方案的 Contextual Embedding（索引期无额外 LLM 调用），再决定是否上 LLM 预生成的 Contextual Retrieval（索引成本更高）。

## Embedding 检查清单

- [ ] 选择支持业务语言的模型（中文场景考虑 BGE-M3、Qwen3-Embedding、GTE-Qwen）。
- [ ] 用 MTEB/MTEB-Chinese 榜单做候选初筛，用自有评估集做最终选型。
- [ ] 对 query 和 chunk 使用同一模型、同一池化策略。
- [ ] 监控 embedding 的 average cosine similarity 分布，发现漂移。
- [ ] embedding 模型版本变更后，全量重建索引或双版本并存。

## Retrieval 检查清单

- [ ] **默认上混合检索（BM25 + Dense + RRF）**，2025 年这已是生产基线，不要裸奔纯 dense。
- [ ] metadata 过滤放在 ANN 搜索之前，减少无效计算。
- [ ] 对复杂查询使用 query rewriting / multi-query 提高召回。
- [ ] 多跳、比较类查询走 Agentic 迭代检索，但必须配置迭代预算。
- [ ] 设置最大检索数量与超时，防止单次请求拖垮系统。

## Reranking 检查清单

- [ ] Reranker 只处理 Top-K 候选，控制在线延迟。
- [ ] 核查 reranker/embedding 许可证：jina-reranker-v3/v3.5 为 CC-BY-NC 非商用许可，商用自托管选 Apache-2.0 的 Qwen3-Reranker 或 BGE-Reranker-v2-m3。
- [ ] 定期用人工标注评估 reranker 的 NDCG 提升。
- [ ] 考虑业务规则（freshness、权威 source）与模型分数的加权。

## Prompt 与生成检查清单

- [ ] Prompt 明确告诉模型“仅基于参考资料回答”。
- [ ] 要求模型输出引用标记，并在后处理中校验引用。
- [ ] 最相关的 chunk 放在 prompt 开头和结尾。
- [ ] 设置较低 temperature，增强事实稳定性。
- [ ] 当检索置信度低时，让模型明确回答“不知道”。

## 评估与迭代检查清单

- [ ] 建立离线评估集，覆盖高频问题、边缘问题、负面案例。
- [ ] 同时看检索指标（Recall@K、MRR）和生成指标（Faithfulness、Relevance）。
- [ ] 用 RGB/RAGTruth 类鲁棒性集定期测噪声与拒答行为。
- [ ] 用 RAGAS 0.4+ 的 collections API 把核心指标嵌入 CI 与在线 trace，而不是一年跑一次离线评测。
- [ ] 收集线上用户反馈，形成闭环。
- [ ] 每次改动（chunk 大小、模型、prompt）都跑 A/B 或 shadow test。
- [ ] Agentic 链路额外跟踪迭代轮数、预算熔断率与每次正确答案成本。

## 常见反模式

| 反模式 | 后果 | 修正 |
|---|---|---|
| Chunk 过大 | 检索精度差、token 浪费 | 按问题粒度切分 |
| 只用 dense 检索 | 漏掉关键词、专有名词 | hybrid retrieval（BM25 + Dense + RRF） |
| 索引期 LLM 调用失控 | 全量 Contextual Retrieval 让索引成本数倍增长 | 先抽样验证收益；优先内生 Contextual Embedding，或只对高价值文档注入 |
| 误用非商用模型权重 | 商用产品踩 CC-BY-NC 许可证红线 | 选型核查许可，优先 Apache-2.0 系 |
| 忽略 metadata | 跨租户/跨版本污染 | 严格 metadata 过滤 |
| 没有 reranker | Top-K 质量不稳定 | 加入轻量 reranker |
| 不做引用校验 | 幻觉引用 | 后处理校验 |
| Agentic 循环无预算 | token 成本失控、延迟不可控 | 最大轮数 + 熔断 + 路由降级 |
| 把 RAG 当万能药 | 创造性任务表现差 | 明确适用边界 |
| 上线后不再迭代 | 效果逐渐衰减 | 建立评估与反馈闭环 |

## 一句话总结

RAG 的最佳实践可以用一句话概括：**小块带上下文、好嵌入、混合召回、轻量重排、严格引用、Agentic 有度、持续评估**。
