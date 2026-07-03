# RAG 流水线

RAG 流水线是用户查询从进入系统到返回答案的完整生命周期。把它建模为状态机，有助于处理重试、改写、多轮检索与失败兜底。

## 流水线状态机

```text
[Receive Query]
     │
     ▼
[Preprocess] ──▶ [Clarify] ──▶ 用户澄清
     │
     ▼
[Retrieve] ──▶ [Empty?] ──▶ [Rewrite/Expand] ──▶ 再次 Retrieve
     │                              │
     ▼                              ▼
[Re-rank]                       [Fallback]
     │
     ▼
[Assemble Context]
     │
     ▼
[Generate] ──▶ [Hallucination Check] ──▶ 后处理
     │
     ▼
[Return Answer + Citations]
```

## 1. 查询接收（Receive Query）

- 支持原始文本、会话历史、多模态输入（图片、语音转写）。
- 附加 context：用户 ID、tenant、权限角色、时间、地理位置。

## 2. 查询预处理（Preprocess）

| 操作 | 目的 |
|---|---|
| 意图识别 | 判断是否需要检索，或可直接闲聊/拒绝 |
| 查询重写 | 把口语化 query 改成适合检索的表达 |
| 查询扩展 | 生成同义词、子问题，提高召回 |
| 敏感词过滤 | 防止检索到受限文档或生成违规内容 |
| 会话上下文压缩 | 把多轮对话提炼为当前检索需求 |

示例：

- 用户问：“这玩意儿怎么退？”
- 改写后：“Acme Corp 的退货政策是什么？”

## 3. 检索（Retrieve）

- 调用 dense、sparse 或 hybrid retriever。
- 应用 metadata 过滤（tenant、source、时间范围）。
- 返回候选 chunks，通常远多于最终进入 prompt 的数量。

**空召回处理**：

- 触发查询改写或扩展。
- 放宽 metadata 过滤。
- 如果仍无结果，进入 fallback：回答“未找到相关资料”。

## 4. 重排（Re-rank）

- 输入：检索 Top-K（如 50 或 100）。
- 输出：更精简的 Top-N（如 5 或 10）。
- 可加入业务规则：优先最新文档、优先权威 source、去重。

## 5. 上下文组装（Assemble Context）

- 按相关性或时间排序 chunks。
- 截断到模型上下文预算，保留系统 prompt 空间。
- 生成引用标记 `[1]`、`[2]`，与 chunk 元数据绑定。

**上下文排序技巧**：

- 最相关的 chunk 放在 prompt 最前和最后。
- 相关性次之的放在中间，降低“中间位置信息丢失”问题。

## 6. 生成（Generate）

- Prompt 模板包含系统角色、参考资料、用户问题、输出格式要求。
- 模型流式输出答案与引用标记。
- 可设置 `temperature` 较低，提高事实稳定性。

## 7. 后处理（Post-process）

| 检查 | 做法 |
|---|---|
| 引用校验 | 确认模型输出的 `[1]` 对应真实 chunk |
| 答案相关性 | 判断答案是否真正回答了 query |
| 幻觉检测 | 用 NLI 模型或 LLM self-check 验证答案是否被上下文支持 |
| 敏感内容过滤 | 再次过滤输出 |

## 8. 返回与观测（Return & Observe）

- 返回答案、引用、置信度、耗时。
- 记录完整 trace：query、rewritten query、retrieved chunks、reranked chunks、generated answer、latency、token usage。

## 失败模式与兜底

| 失败场景 | 兜底策略 |
|---|---|
| 检索空结果 | 查询改写 → 放宽过滤 → 回答“不知道” |
| 检索结果不相关 | 多路召回 → Reranker 过滤 → 降低置信度 |
| 模型生成偏离上下文 | 引用校验 + 后处理拒绝 |
| 延迟过高 | 超时后返回缓存结果或降级为纯检索列表 |
| 向量库故障 | 切换只读副本或 fallback 到关键词索引 |

## 小结

RAG 流水线不是单线程的一次调用，而是一个可以**循环、分支、降级**的状态机。设计时要为每个状态预留观测点与兜底路径，才能保证线上稳定。
