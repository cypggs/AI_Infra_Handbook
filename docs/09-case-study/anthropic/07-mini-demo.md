# Mini Demo

本章介绍 `docs/09-case-study/anthropic/mini-demo/` 中的迷你示例。它复现 Anthropic 推理与对齐工程中最具辨识度的两个机制：**prompt caching**（prefix hash + 20-block lookback + TTL + 成本计量）与 **Constitutional AI 的 critique-revise 循环**（SL 阶段）。

## 场景

一个名为 `anthropic-mini` 的包提供：

1. **Prompt Cache 模拟器**（`cache.py`）：忠实复现 Claude 官方的缓存命中模型——缓存只在断点写入、读取向前回看 20 个 block、5m/1h 双 TTL、workspace 级隔离，并按官方定价倍率（读 0.1x / 5m 写 1.25x / 1h 写 2x）计算成本。
2. **Constitutional critique-revise**（`constitution.py`）：给定一组宪法原则，对模型回答做 critique 并 revise（确定性、规则化，无需 LLM key）。
3. **Anthropic 风格 `/v1/messages` 端点**（`server.py`）：FastAPI 服务，用 `x-api-key` 认证，支持顶层 `cache_control`（自动缓存）与 block 级断点，返回带 `cache_creation_input_tokens` / `cache_read_input_tokens` 的 `usage`。

## 目录结构

```text
mini-demo/
├── pyproject.toml
├── README.md
├── anthropic_mini/
│   ├── __init__.py
│   ├── cache.py          # PromptCache：prefix hash + lookback + TTL + 成本
│   ├── constitution.py   # 宪法原则 + critique + revise
│   ├── generator.py      # 模拟生成（确定性）
│   └── server.py         # FastAPI /v1/messages + cache_control
└── tests/
    ├── __init__.py
    ├── test_cache.py
    ├── test_constitution.py
    └── test_server.py
```

## 安装

```bash
cd docs/09-case-study/anthropic/mini-demo
pip install -e ".[dev]"
```

## 运行服务

```bash
uvicorn anthropic_mini.server:app --port 8000
```

## 测试接口

非缓存请求：

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-demo" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-haiku-mini",
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

带 prompt caching（顶层自动缓存）：

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-demo" \
  -d '{
    "model": "claude-haiku-mini",
    "max_tokens": 64,
    "cache_control": {"type": "ephemeral"},
    "system": "You are a helpful, honest, harmless assistant.",
    "messages": [{"role": "user", "content": "Summarize RAG in one line."}]
  }'
```

第二次发同样请求时，`usage.cache_read_input_tokens` 将大于 0，`cache_creation_input_tokens` 为 0。

## 测试

```bash
pytest tests/ -q
```

## 关键代码片段

### 1. 前缀 hash + 20-block 回看命中

```python
def process(self, blocks, breakpoint_idx, workspace, ttl=TTL_5M):
    # 向前回看最多 20 个 block，寻找之前写过的匹配条目
    hit = None
    start = max(-1, breakpoint_idx - LOOKBACK)
    for i in range(breakpoint_idx, start, -1):
        if self._lookup(workspace, blocks[i].prefix_hash):
            hit = i
            break
    read  = sum(b.tokens for b in blocks[:hit + 1])            # 0.1x
    write = sum(b.tokens for b in blocks[hit + 1:breakpoint_idx + 1])  # 1.25x/2x
    after = sum(b.tokens for b in blocks[breakpoint_idx + 1:])        # 1x
    self._write(workspace, blocks[breakpoint_idx].prefix_hash, ttl)
    return Usage(read, write, after)
```

### 2. Constitutional critique-revise

```python
def revise(response, constitution):
    for principle in constitution:
        critique = principle.critique(response)      # 命中则返回批评文本
        if critique:
            response = principle.apply(response)     # 规则化修订
    return response
```

### 3. 成本计算（官方倍率）

```python
def cost(usage, base_per_mtok):
    return (
        usage.cache_read  * 0.10 * base_per_mtok / 1e6   # 读 0.1x
      + usage.write_5m   * 1.25 * base_per_mtok / 1e6   # 5m 写 1.25x
      + usage.write_1h   * 2.00 * base_per_mtok / 1e6   # 1h 写 2x
      + usage.input      * 1.00 * base_per_mtok / 1e6
    )
```

## 与生产系统的差异

| 方面 | Mini Demo | Anthropic 生产 |
|---|---|---|
| 缓存存储 | 进程内 dict | 分布式内存缓存 + workspace/org 隔离 |
| 命中判定 | SHA prefix hash + 20-block lookback | 同模型，工程化、可观测、支持诊断 |
| 对齐 | 规则化 critique-revise | Constitutional SL + RLAIF + RL |
| 认证 | 单一 `x-api-key` | workspace/org + 细粒度权限 |
| 部署 | 单进程 | 三云多区域 Trainium/GPU 集群 |
| 安全 | 无 | ASL 分类器、红队、权重安全、审计 |

## 扩展练习

1. 把缓存存储换成 Redis，支持跨进程 workspace 隔离。
2. 实现"varying suffix 陷阱"：把 `cache_control` 放在每请求变化的块上，观察零命中并修复。
3. 用真实小模型（如本地 llama.cpp）替换 `constitution.revise` 的规则化逻辑。
4. 增加 cache 命中率、TTFT、成本指标的 Prometheus 导出。

## 小结

Mini Demo 把 Anthropic 两个最工程化的思想——**prompt caching 的精确命中模型**与**Constitutional critique-revise**——变成可运行、可测试的代码。它是理解"Claude 推理为什么便宜"与"对齐如何管线化"的动手沙盒。
