# KV Cache 管理 Mini Demo

纯 Python（无 GPU、无第三方运行时依赖）模拟 LLM 推理中 KV Cache 基础设施层的四个核心机制：

| 模块 | 模拟对象 | 对应真实系统 |
|---|---|---|
| `kv_cache_mini/block.py` | paged KV block 分配器：引用计数、copy-on-write、LRU 逐出 | vLLM v1 PagedAttention `BlockTable` |
| `kv_cache_mini/prefix.py` | radix tree 前缀缓存：跨请求共享、LRU 逐出 | SGLang RadixAttention / vLLM prefix caching |
| `kv_cache_mini/tier.py` | GPU/CPU/SSD 三层缓存：迁移成本模型、命中收益 | LMCache、SGLang HiCache、Dynamo KVBM |
| `kv_cache_mini/migrate.py` | PD 分离下的 KV 传输调度：流水线重叠 vs 串行 | Mooncake Transfer Engine、NIXL、vLLM KV connector |
| `kv_cache_mini/demo.py` | 5 个端到端场景 | — |

## 快速开始

```bash
cd docs/04-llmops/kv-cache/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m kv_cache_mini.demo
```

## 场景说明

1. **block_allocator**：2 条序列 fork 共享 2 个 block，写时复制触发 COW；释放后强制逐出 LRU block。
2. **radix_prefix**：64 token 系统提示在 3 条请求间复用，命中前缀免 prefill。
3. **tiered_cache**：回放包含重复前缀的访问序列，统计各层命中率、降级次数与相对全量 prefill 的收益。
4. **pd_migration**：64 个 1 MiB block 经 2 条流从 prefill 节点搬到 decode 节点，对比流水线与串行的 TTFT。
5. **kv_economics**：以 Llama-3.1-70B 类配置（80 层、8 KV heads、head_dim 128）计算每 token KV 占用：FP16 320 KiB、FP8 160 KiB、INT4 80 KiB；128K 上下文单序列分别为 40/20/10 GiB。

## 运行测试

```bash
pytest tests/ -v
```
