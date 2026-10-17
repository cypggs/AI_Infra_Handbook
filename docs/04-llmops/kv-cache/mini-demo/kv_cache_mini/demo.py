"""端到端演示：KV Cache 管理的五个核心场景。

运行：
    python -m kv_cache_mini.demo
"""

from __future__ import annotations

from kv_cache_mini.block import BlockAllocator, BlockTable
from kv_cache_mini.migrate import PDScheduler, TransferEngine
from kv_cache_mini.prefix import RadixTree
from kv_cache_mini.tier import TieredCache, TierSpec


def kv_bytes_per_token(
    num_layers: int,
    num_kv_heads: int,
    head_dim: int,
    dtype_bytes: int = 2,
) -> int:
    """单个 token 的 KV 占用：2(K+V) × 层数 × kv heads × head dim × 字节数。"""
    return 2 * num_layers * num_kv_heads * head_dim * dtype_bytes


# ----------------------------------------------------------------------
def scenario_block_allocator() -> dict:
    """场景 1：paged block 分配、fork 共享、COW 与 LRU 逐出。"""
    alloc = BlockAllocator(num_blocks=4, block_size=16)
    main = BlockTable(alloc)
    main.append_tokens(32)  # 2 blocks
    branch = main.fork()    # 共享 2 blocks
    main.write(0)           # 写共享块触发 COW
    result = {
        "num_used": alloc.num_used,
        "copies": alloc.copies,
        "refcounts": [alloc.refcount(b) for b in main.blocks + branch.blocks],
    }
    branch.release()
    # 强制逐出：空闲池只有 1 个 block，再申请 2 个时触发 LRU 逐出
    others = [BlockTable(alloc) for _ in range(2)]
    for t in others:
        t.append_tokens(16)
    result["evictions"] = alloc.evictions
    result["num_free_after"] = alloc.num_free
    return result


def scenario_radix_prefix() -> dict:
    """场景 2：system prompt 前缀在多条请求间复用。"""
    tree = RadixTree()
    system_prompt = list(range(0, 64))        # 64 token 的系统提示
    req_a = system_prompt + [100, 101, 102]   # 请求 A
    req_b = system_prompt + [200, 201]        # 请求 B：共享系统提示
    hit_a = tree.insert(req_a)
    hit_b = tree.insert(req_b)
    hit_c = tree.match(system_prompt + [999])  # 新请求仍命中系统提示
    return {
        "hit_a": hit_a,
        "hit_b": hit_b,
        "hit_new": hit_c,
        "tokens_cached": tree.total_tokens(),
        "nodes": tree.num_nodes(),
    }


def scenario_tiered_cache() -> dict:
    """场景 3：三层缓存回放访问序列，统计命中与收益。"""
    cache = TieredCache(
        gpu=TierSpec("gpu", capacity_blocks=4, read_cost_per_block=0.0001,
                     write_cost_per_block=0.0002),
        cpu=TierSpec("cpu", capacity_blocks=8, read_cost_per_block=0.002,
                     write_cost_per_block=0.002),
        ssd=TierSpec("ssd", capacity_blocks=16, read_cost_per_block=0.02,
                     write_cost_per_block=0.02),
        prefill_cost_per_block=0.05,
    )
    prefix_a = [f"a{i}" for i in range(4)]   # 请求 A 的前缀（4 blocks）
    prefix_b = [f"b{i}" for i in range(4)]   # 请求 B 的前缀
    trace = (
        prefix_a + ["a_gen"]          # A 首访
        + prefix_b + ["b_gen"]        # B 首访
        + prefix_a + ["a_gen2"]       # A 重访：命中
        + prefix_b + ["b_gen2"]       # B 重访：命中
        + prefix_a                    # A 再访：命中
        + [f"c{i}" for i in range(6)] # 全新长请求：挤占并触发降级
        + prefix_a                    # A 又访：可能落在慢层
    )
    for key in prefix_a + prefix_b:
        cache.put(key)
    return cache.simulate(trace)


def scenario_pd_migration() -> dict:
    """场景 4：PD 分离下流水线传输 vs 串行传输的 TTFT。"""
    engine = TransferEngine(bandwidth_bytes_per_s=25e9, num_streams=2)
    sched = PDScheduler(
        engine=engine,
        num_blocks=64,            # 64 个 1 MiB block（约 1k token 上下文 @ 16 tok/block）
        block_bytes=1 << 20,
        decode_time_per_block=0.004,
    )
    pipelined = sched.simulate_pipelined()
    return {
        "per_block_transfer_ms": sched.per_block_transfer_s * 1000,
        "sequential_ttft_ms": sched.sequential_ttft_s() * 1000,
        "pipelined_ttft_ms": pipelined["ttft_s"] * 1000,
        "pipelined_makespan_ms": pipelined["makespan_s"] * 1000,
        "overlap_gain_ms": sched.overlap_gain_s() * 1000,
    }


def scenario_kv_economics() -> dict:
    """场景 5：KV 经济学——每 token 占用与量化收益。"""
    # 以 Llama-3.1-70B 类配置为例：80 层、GQA 8 个 KV head、head_dim 128
    layers, kv_heads, head_dim = 80, 8, 128
    per_tok_fp16 = kv_bytes_per_token(layers, kv_heads, head_dim, 2)
    per_tok_fp8 = kv_bytes_per_token(layers, kv_heads, head_dim, 1)
    per_tok_int4 = kv_bytes_per_token(layers, kv_heads, head_dim, 1) // 2
    ctx = 128 * 1024
    return {
        "bytes_per_token_fp16": per_tok_fp16,
        "bytes_per_token_fp8": per_tok_fp8,
        "bytes_per_token_int4": per_tok_int4,
        "gib_per_seq_128k_fp16": round(per_tok_fp16 * ctx / (1 << 30), 1),
        "gib_per_seq_128k_fp8": round(per_tok_fp8 * ctx / (1 << 30), 1),
        "gib_per_seq_128k_int4": round(per_tok_int4 * ctx / (1 << 30), 1),
    }


# ----------------------------------------------------------------------
def run_demo() -> dict:
    scenarios = {
        "1_block_allocator": scenario_block_allocator(),
        "2_radix_prefix": scenario_radix_prefix(),
        "3_tiered_cache": scenario_tiered_cache(),
        "4_pd_migration": scenario_pd_migration(),
        "5_kv_economics": scenario_kv_economics(),
    }
    for name, result in scenarios.items():
        print(f"\n=== {name} ===")
        for k, v in result.items():
            print(f"  {k}: {v}")
    return scenarios


if __name__ == "__main__":
    run_demo()
