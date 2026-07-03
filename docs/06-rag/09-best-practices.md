# 最佳实践

RAG 系统的效果往往取决于大量细节。本章整理了一份可直接落地的检查清单和常见反模式。

## Chunking 检查清单

- [ ] Chunk 能独立回答一类常见问题，不依赖上下文补全。
- [ ] 相邻 chunk 保留适当重叠（通常 10%~20%），避免语义断裂。
- [ ] 对结构化文档优先按标题/章节切分，而不是纯按长度。
- [ ] 保留 metadata（source、section、page、updated_at）。
- [ ] 对表格、代码等特殊内容使用专用切分策略。

## Embedding 检查清单

- [ ] 选择支持业务语言的模型（中文场景考虑 BGE-M3、GTE）。
- [ ] 对 query 和 chunk 使用同一模型、同一池化策略。
- [ ] 监控 embedding 的 average cosine similarity 分布，发现漂移。
- [ ] embedding 模型版本变更后，全量重建索引或双版本并存。

## Retrieval 检查清单

- [ ] 至少同时评估 dense 与 keyword 召回率，选择混合策略。
- [ ] metadata 过滤放在 ANN 搜索之前，减少无效计算。
- [ ] 对复杂查询使用 query rewriting / multi-query 提高召回。
- [ ] 设置最大检索数量与超时，防止单次请求拖垮系统。

## Reranking 检查清单

- [ ] Reranker 只处理 Top-K 候选，控制在线延迟。
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
- [ ] 收集线上用户反馈，形成闭环。
- [ ] 每次改动（chunk 大小、模型、prompt）都跑 A/B 或 shadow test。

## 常见反模式

| 反模式 | 后果 | 修正 |
|---|---|---|
| Chunk 过大 | 检索精度差、token 浪费 | 按问题粒度切分 |
| 只用 dense 检索 | 漏掉关键词、专有名词 | hybrid retrieval |
| 忽略 metadata | 跨租户/跨版本污染 | 严格 metadata 过滤 |
| 没有 reranker | Top-K 质量不稳定 | 加入轻量 reranker |
| 不做引用校验 | 幻觉引用 | 后处理校验 |
| 把 RAG 当万能药 | 创造性任务表现差 | 明确适用边界 |
| 上线后不再迭代 | 效果逐渐衰减 | 建立评估与反馈闭环 |

## 一句话总结

RAG 的最佳实践可以用一句话概括：**小块、好嵌入、混合召回、轻量重排、严格引用、持续评估**。
