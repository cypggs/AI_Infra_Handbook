# 9. 最佳实践

> 一句话理解：**Agent Memory 的最佳实践不是把一切都记下来，而是“分层记忆、按需检索、主动遗忘、严控隐私”，让记忆系统成为 Agent 的助力而不是负担**。

## 1. 按记忆类型选存储

不要所有记忆都塞进同一个数据库。

| 记忆类型 | 推荐存储 | 不要这样做 |
|---|---|---|
| Working Memory | 内存 / Redis | 写入 Postgres 增加延迟 |
| Short-term Memory | Redis / 内存 | 长期保留所有会话摘要 |
| Semantic Memory | 向量 DB | 只用关键词检索 |
| Episodic Memory | 向量 DB + 文档 DB | 只存成功 episode，忽略失败 |
| Procedural Memory | KV Store / Postgres | 把流程模板当作普通语义记忆 |

核心原则：**记忆的寿命、检索方式与一致性要求决定了它的存储形态**。

## 2. 控制上下文长度

再强大的 LLM 也有上下文限制，回注记忆时必须精打细算。

### 推荐策略

- **预分配预算**：给 system prompt、working memory、retrieved memories 分别设置 token 上限。
- **优先级排序**：工作记忆 > 短期摘要 > 高相关长期记忆 > 情景记忆。
- **Rerank 后截断**：不要直接把向量检索的 top-k 全塞进去，先 rerank 再按预算截断。
- **避免重复**：合并语义相似的记忆，减少冗余。

### 上下文预算示例

```text
总上下文窗口: 128K tokens
- system prompt: 2K
- working memory: 30K
- short-term summary: 4K
- retrieved long-term memories: 8K
- tool schemas + current task: 剩余
```

## 3. 避免记忆污染

记忆污染是指把错误、幻觉、低质量信息存入长期记忆，导致后续回答持续出错。

### 污染源

| 来源 | 示例 |
|---|---|
| 工具错误结果 | 数据库返回空被误解为“没有数据” |
| 模型幻觉 | Agent 编造不存在的事实 |
| 用户错误输入 | 用户随口一说被当作偏好 |
| 对抗输入 | 提示注入试图污染长期记忆 |

### 应对策略

- **置信度过滤**：只对高置信度信息做长期存储。
- **用户确认**：关键偏好让用户明确确认后再写入。
- **来源标记**：每条记忆记录来源，便于追溯与删除。
- **定期审计**：抽样检查长期记忆质量。
- **输入护栏**：写入前检测提示注入与敏感信息。

## 4. Embedding 版本管理

Embedding 模型升级是生产中的常见操作，处理不好会导致检索质量断崖式下降。

### 推荐做法

- 每条记忆记录 `embedding_model` 与 `embedding_version`。
- 模型升级时，先双写新旧向量，逐步切换检索。
- 不要直接在新索引上用旧向量检索。
- 监控新旧模型检索质量的 A/B 差异。

### 版本标记示例

```json
{
  "id": "mem-001",
  "text": "...",
  "embedding": [...],
  "embedding_model": "text-embedding-3-small",
  "embedding_version": "2024-07",
  "created_at": "2026-07-01T10:00:00Z"
}
```

## 5. 敏感信息过滤

敏感信息一旦进入长期记忆，很难彻底清除。

### 推荐做法

- **写入前检测**：使用 PII 检测模型或规则引擎。
- **分类标签**：给记忆打 `sensitivity` 标签（low/medium/high）。
- **高敏感拒绝写入**：密码、Token、密钥、验证码绝不入长期记忆。
- **中敏感脱敏**：姓名、电话、地址可脱敏后存储。
- **用户删除权**：提供查看、修改、删除记忆的接口。

```python
class PrivacyFilter:
    def check(self, text: str) -> FilterResult:
        if contains_secret(text):
            return FilterResult(reject=True, reason="secret_detected")
        if contains_pii(text):
            return FilterResult(allow=True, sanitized=mask_pii(text))
        return FilterResult(allow=True)
```

## 6. 评测记忆系统

没有评测的记忆优化是盲调。

### 评测维度

| 维度 | 说明 | 指标 |
|---|---|---|
| **Recall 命中率** | query 能否找到相关记忆 | hit@k、MRR |
| **Precision** | 检索结果中有多少真正相关 | precision@k |
| **Coverage** | 多少用户偏好/事实被成功记住 | 覆盖率 |
| **Contamination** | 记忆库中错误/低质量记录比例 | 错误率 |
| **Latency** | 检索与写入延迟 | P50/P99 |
| **Privacy** | 敏感信息拦截率 | 拦截率 |

### 评测方法

- 构建标准 query-memory 对，测试检索命中率。
- 人工抽查长期记忆，评估质量。
- 在真实任务中对比“有记忆”与“无记忆”的表现差异。
- 用影子运行做回归测试。

## 7. 不要过度设计

记忆系统的复杂度应该与场景匹配。

### 何时简单即可

- 单次会话、无跨会话需求：只需要 Working Memory。
- 用户少、偏好简单：用 KV Store 存用户配置即可。
- 任务简单、无需经验复用：不需要 Episodic Memory。

### 何时需要完整 Memory 系统

- 多会话、多任务、多用户。
- 需要个性化与经验复用。
- 任务长周期、需要 checkpoint。
- 企业级隐私与审计要求。

## 8. 多 Agent 协作中的记忆

多 Agent 场景下，记忆可以是共享的也可以是隔离的。

| 模式 | 说明 | 风险 |
|---|---|---|
| **共享记忆池** | 多个 Agent 共用长期记忆 | 需要严格权限控制 |
| **Agent 私有记忆** | 每个 Agent 有自己的记忆 | 协作效率低 |
| **层级记忆** | 团队级共享 + Agent 私有 + 用户私有 | 复杂度最高 |

推荐从“用户级共享 + Agent 私有”开始，根据协作需求逐步扩展。

## 最佳实践速查表

| 维度 | 推荐做法 |
|---|---|
| 存储 | 按记忆类型选存储，不要一刀切 |
| 上下文 | 预分配预算、rerank、截断、去重 |
| 污染 | 置信度过滤、用户确认、来源标记、输入护栏 |
| Embedding | 版本标记、双写过渡、A/B 监控 |
| 隐私 | 写入前检测、敏感信息拒绝、用户删除权 |
| 评测 | hit@k、precision、contamination、latency |
| 复杂度 | 按需选型，避免过度设计 |
| 多 Agent | 从用户级共享 + Agent 私有开始 |

## 本章小结

Agent Memory 的最佳实践围绕“分层、检索、遗忘、隐私、评测”五个关键词展开：按记忆类型选存储，控制上下文预算，避免记忆污染，管理 embedding 版本，严格过滤敏感信息，建立评测体系，不过度设计，并在多 Agent 场景中谨慎规划记忆共享边界。好的记忆系统不是记住最多，而是记住最对、遗忘最及时、保护最到位。

**参考来源**

- [Mem0 Best Practices](https://docs.mem0.ai)
- [LangGraph Production Concepts](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Letta Memory Guidelines](https://docs.letta.com)
- [Steve Kinney — Agent Memory Systems](https://stevekinney.com/writing/agent-memory-systems)
