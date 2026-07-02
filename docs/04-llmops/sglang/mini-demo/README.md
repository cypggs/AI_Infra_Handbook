# Mini SGLang

一个用于教学的简化版 SGLang 实现，展示两个核心思想：

1. **RadixAttention**：用 Radix Tree 自动复用多请求之间的公共前缀。
2. **Structured Generation**：用 FSM 约束每步可生成的 token，使输出符合正则表达式。

> **注意**：这是教学演示，不是生产可用的推理引擎。真实 SGLang 依赖 GPU、CUDA kernel、完整的 Transformer 实现以及 xgrammar 等结构化解码库。

## 环境要求

- Python >= 3.9
- CPU 即可运行

## 安装

```bash
cd docs/04-llmops/sglang/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 运行 Demo

```bash
python -m sglang_mini.demo
```

## 运行测试

```bash
pytest tests/ -q
```

## 文件说明

| 文件 | 职责 |
|---|---|
| `sglang_mini/radix_tree.py` | Radix Tree：前缀匹配、插入、引用计数、LRU 回收 |
| `sglang_mini/cache_manager.py` | 基于 Radix Tree 的 dummy KV Cache 管理器 |
| `sglang_mini/fsm.py` | 简化 regex 到 NFA 的编译器 |
| `sglang_mini/structured_sampler.py` | 结合 FSM 与 logits 的约束采样器 |
| `sglang_mini/runtime.py` | 简单 Runtime：调度 + cache + 采样 |
| `sglang_mini/dummy_model.py` | 生成 dummy logits 的小模型 |
| `sglang_mini/demo.py` | 入口脚本，演示前缀共享与结构化生成 |
| `tests/test_radix_tree.py` | Radix Tree 单元测试 |
| `tests/test_structured_sampler.py` | FSM 约束采样单元测试 |

## 与真实 SGLang 的区别

| 方面 | Mini Demo | 真实 SGLang |
|---|---|---|
| 模型 | Dummy 小模型 | 真实 Transformer |
| Attention | 未实现 | FlashInfer / FlashAttention / MLA |
| Radix Tree | 纯 Python | C++/CUDA 高性能实现（HiCache / UnifiedRadixTree） |
| 结构化 | 简化 regex | xgrammar / outlines 完整集成 |
| Runtime | 单线程模拟 | 多进程、异步、编译优化 |

## 学习目标

- 理解为什么 Radix Tree 能比 Block Table 更细粒度地复用前缀。
- 理解结构化生成如何通过 FSM 在采样阶段强制输出合法。
- 能够定位真实 SGLang 中对应的源码模块。
