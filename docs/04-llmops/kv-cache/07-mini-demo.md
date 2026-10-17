# 7. 工程实践：Mini Demo

> 一句话理解：这个 Mini Demo 用纯 Python（无 GPU、无第三方运行时依赖）模拟 KV 缓存基础设施层的四类核心机制——paged block 分配、radix 前缀缓存、三层缓存成本模型、PD 分离传输调度，全部数字确定性可复现。

## 7.1 Demo 设计

真实系统的对应关系：

| Demo 模块 | 模拟对象 | 真实系统 |
|---|---|---|
| `kv_cache_mini/block.py` | paged block 分配：引用计数、COW、LRU 逐出 | vLLM v1 `BlockManager` |
| `kv_cache_mini/prefix.py` | radix tree 前缀匹配：插入分裂、叶子 LRU 逐出 | SGLang RadixAttention |
| `kv_cache_mini/tier.py` | GPU/CPU/SSD 三层缓存：降级/提升、迁移成本模型 | LMCache / SGLang HiCache |
| `kv_cache_mini/migrate.py` | PD 分离 KV 传输：流水线重叠 vs 串行 | Mooncake TE / NIXL |

## 7.2 目录结构

```text
docs/04-llmops/kv-cache/mini-demo/
├── README.md
├── pyproject.toml
├── kv_cache_mini/
│   ├── __init__.py
│   ├── block.py      # BlockAllocator + BlockTable（COW/LRU 逐出）
│   ├── prefix.py     # RadixTree（最长前缀匹配、插入分裂、叶子 LRU 逐出）
│   ├── tier.py       # TierSpec + TieredCache（三层、降级瀑布、命中收益）
│   ├── migrate.py    # TransferEngine + PDScheduler（流水线 TTFT 模型）
│   └── demo.py       # 5 个端到端场景
└── tests/
    ├── test_block.py    # 18 个用例
    ├── test_prefix.py   # 12 个用例
    ├── test_tier.py     # 12 个用例
    ├── test_migrate.py  # 12 个用例
    └── test_demo.py     # 8 个用例
```

## 7.3 快速运行

```bash
cd docs/04-llmops/kv-cache/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m kv_cache_mini.demo
```

## 7.4 五个场景与实测输出

### 场景 1：block 分配、fork 共享与 COW

2 条序列 fork 共享 2 个 block（引用计数变为 2），父序列写第一个位置触发一次 copy-on-write（实际复制 1 次）；子序列释放后，强制申请新 block 触发 1 次 LRU 逐出：

```text
num_used: 3          copies: 1          refcounts: [1, 2, 1, 2]
evictions: 1         num_free_after: 0
```

### 场景 2：system prompt 前缀复用

64 token 的系统提示 + 两条不同请求：第一条零命中，第二条命中全部 64 token（免 prefill）；任意新请求也命中 64 token。Radix tree 在分叉处自动分裂（公共段 + 两条叶子）：

```text
hit_a: 0    hit_b: 64    hit_new: 64
tokens_cached: 69 (= 64 公共段 + 3 + 2 两条叶子)    nodes: 4
```

### 场景 3：三层缓存成本模型

GPU(4)/CPU(4)/SSD(16) 三层，回放含重复前缀的 34 次访问：

```text
hit_rate: 0.7059     hits: {cpu: 20, gpu: 4}     misses: 10
demotions: {gpu->cpu: 24}    occupancy: {gpu: 4, cpu: 4, ssd: 0}
total_cost_s: 0.046      saved_prefill_s: 1.2      savings_s: 1.154
```

读法：70.6% 的访问命中缓存，省下 1.2 秒的 prefill 计算，支付 0.046 秒的搬运成本，净赚 1.154 秒——分层缓存的「收益 ≫ 成本」在这组参数下成立。

### 场景 4：PD 分离传输调度

64 个 1 MiB block 经 2 条流（各 25 GB/s）从 prefill 节点搬到 decode 节点，decode 每 block 耗时 4 ms：

```text
per_block_transfer_ms: 0.0419
sequential_ttft_ms: 6.68        # 全部传完再解码
pipelined_ttft_ms: 4.04         # 首 block 到达即解码
pipelined_makespan_ms: 256.04
overlap_gain_ms: 2.64
```

读法：流水线把 TTFT 中「等 KV」的部分从 6.68 ms 压到 0.042 ms——decode 等待时间几乎消失，剩下的是解码本身。

### 场景 5：KV 经济学

Llama-3.1-70B 类配置（80 层、8 KV heads、head_dim 128）：

```text
bytes_per_token_fp16: 327680    bytes_per_token_fp8: 163840    bytes_per_token_int4: 81920
gib_per_seq_128k_fp16: 40.0    gib_per_seq_128k_fp8: 20.0    gib_per_seq_128k_int4: 10.0
```

读法：FP8 KV 量化把单条 128K 请求的 KV 从 40 GiB 压到 20 GiB——显存省一半，传输与分层搬运同比例变快。

## 7.5 可做的扩展练习

1. 给 `TieredCache` 加 LFU 逐出策略，与 LRU 对比同一 trace 的命中率；
2. 给 `PDScheduler` 加「层间交错」模型（按 transformer 层而非 token block 流水）；
3. 在 `RadixTree` 上实现 block 粒度对齐（token 数取整到 block_size）；
4. 把 `BlockAllocator` 的逐出策略换成「下沉优先」（逐出时先写慢层再释放）。
