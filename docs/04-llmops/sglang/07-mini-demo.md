# 7. 工程实践：Mini SGLang

本章实现一个教学版 Mini SGLang，核心目标是理解 **RadixAttention 的 Radix Tree 前缀缓存** 与 **结构化生成中的 FSM 约束采样**。

## 设计目标

- 不依赖 GPU，使用 PyTorch CPU 即可运行
- 代码控制在 500~1500 行
- 展示 Radix Tree 的插入、前缀匹配、引用计数与回收
- 展示正则约束如何限制每步可采样 token
- 与真实 SGLang 的区别在 README 中说明

## 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── sglang_mini/
│   ├── __init__.py
│   ├── radix_tree.py          # Radix Tree 实现
│   ├── cache_manager.py       # 基于 Radix Tree 的 KV Cache 管理器
│   ├── fsm.py                 # 简化 regex -> NFA
│   ├── structured_sampler.py  # FSM 约束采样器
│   ├── runtime.py             # 简单 Runtime
│   ├── dummy_model.py         # Dummy 模型
│   └── demo.py                # 入口演示
└── tests/
    ├── test_radix_tree.py
    └── test_structured_sampler.py
```

## 核心设计

### 1. Radix Tree

每个节点保存一个 token 到子节点的映射。`match_prefix` 沿 token 序列下行，返回最长匹配长度与终止节点；`insert` 复用已有前缀，只为 suffix 创建新节点。

```python
class RadixTree:
    def match_prefix(self, token_ids):
        ...
    def insert(self, token_ids, value):
        ...
```

### 2. RadixCacheManager

在 Radix Tree 之上封装请求生命周期：

- `prepare_request`：匹配前缀，为 suffix 分配 dummy KV 条目。
- `commit_request`：请求结束后把完整序列插入树中。
- `release_request`：降低引用计数，允许 LRU 回收。

### 3. FSM

支持一个小子集的正则表达式：

- 字面量：`A`、`b`
- 字符类：`\d`
- 分组：`(A|B)`
- 重复：`+`、`*`、`?`、`{n}`

使用 Thompson 构造法生成 NFA，每步通过 ε-closure 模拟。

### 4. StructuredSampler

结合 FSM 与模型 logits：

1. 根据当前 FSM 状态计算合法 token 集合。
2. 把非法 token 的 logits 置为 `-inf`。
3. 从剩余分布中采样。

## 运行方式

```bash
cd docs/04-llmops/sglang/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m sglang_mini.demo
pytest tests/
```

## 预期输出

```
=== Demo 1: RadixAttention prefix sharing ===

[req-1] prefix_len=0
[req-1] generated: ...
[req-2] prefix_len=52 (system prompt shared!)
...
Prefix hit rate: 43.7%

=== Demo 2: Structured generation (regex constraint) ===

Pattern: \d{4}-\d{2}-\d{2}
Generated: 2026-07-02
Matches regex? True

=== Demo 3: Structured generation (simple alternation) ===

Pattern: (red|blue|green)
Generated: green
```

## 完整代码

完整代码详见 [mini-demo/README.md](./mini-demo/README.md)。

## 本章小结

Mini Demo 的价值不在于性能，而在于把 SGLang 最核心的两个机制（RadixAttention + Structured Generation）从源码中抽象出来，让人能用几十行代码看懂设计本质。
