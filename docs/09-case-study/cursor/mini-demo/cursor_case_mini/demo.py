"""5 个端到端演示场景（确定性输出，供 07-mini-demo.md 逐字引用）。

场景 1  代码库索引：chunk -> Merkle 增量同步 -> 向量检索
场景 2  Tab 延迟预算分解与 P50/P95
场景 3  Speculative Edits 命中率与加速比（扫改动率）
场景 4  后台 Agent 沙箱配额调度
场景 5  订阅推理经济学：盈亏平衡与毛利率
"""

from __future__ import annotations

from .economics import (
    COST_PER_COMMIT,
    break_even_requests,
    monthly_margin,
    request_cost,
    routing_savings,
    tab_serving_cost_day,
)
from .indexing import CodebaseIndex
from .latency import TAB_BUDGET, legacy_budget, sample_end_to_end, sensitivity, top_stages, total_ms
from .sandbox import Host, Sandbox, run_workload
from .speculative import ApplyEngine, scan_edit_rate


def scenario_indexing() -> str:
    files = {
        "src/db.py": "def connect(host):\n    return Client(host)\n\n\ndef query(sql):\n    return conn.execute(sql)\n\n\nclass Pool:\n    def __init__(self, size):\n        self.size = size\n",
        "src/api.py": "from db import connect\n\n\ndef handler(req):\n    conn = connect('localhost')\n    return conn.query(req.sql)\n\n\ndef health():\n    return 'ok'\n",
        "README.md": "# demo\n\n这是一个演示项目。\n\n## 使用\n\n运行 api.py。\n",
    }
    idx = CodebaseIndex()
    first = idx.sync(files)
    # 修改一个文件 + 删除一个文件
    files["src/db.py"] = files["src/db.py"] + "\ndef close(conn):\n    conn.close()\n"
    del files["README.md"]
    second = idx.sync(files)
    hits = idx.search("如何建立数据库连接 connect", k=2)
    st = idx.stats()
    lines = [
        f"场景1 代码库索引管道",
        f"  首次同步: {first}",
        f"  二次同步(改 1 文件删 1 文件): {second}",
        f"  索引规模: {st}",
        f"  检索 '如何建立数据库连接 connect' top-2:",
    ]
    for r in hits:
        lines.append(
            f"    命中 混淆路径={r.obfuscated_path[:16]}... 行 {r.start_line}-{r.end_line}"
        )
    return "\n".join(lines)


def scenario_latency() -> str:
    cur = sample_end_to_end()
    legacy_total = total_ms(legacy_budget())
    lines = [
        "场景2 Tab 补全延迟预算（教学预算，合计 %.0f ms，官方口径：更新后约 260 ms）" % total_ms(),
        "  阶段拆解: " + "; ".join(f"{k} {v:.0f}ms" for k, v in TAB_BUDGET.items()),
        f"  更新前口径同结构合计: {legacy_total:.0f} ms（官方口径约 475 ms）",
        f"  端到端样本(n=10000, seed=42): mean {cur['mean']:.1f} p50 {cur['p50']:.1f} p95 {cur['p95']:.1f} p99 {cur['p99']:.1f}",
        "  贡献前三: " + "; ".join(f"{k} {v:.0f}ms" for k, v in top_stages()),
        f"  Prefill 若省 50ms: 端到端下降 {sensitivity('Prefill(长上下文填充,预填 hungry)', 50):.1f}%",
    ]
    return "\n".join(lines)


def scenario_speculative() -> str:
    engine = ApplyEngine()
    rows = scan_edit_rate()
    lines = ["场景3 Speculative Edits（8192 token 整文件重写）", "  改动率 -> 命中率/加速比:"]
    for rate, hit, speedup in rows:
        lines.append(f"    改动率 {rate:.0%}: 命中率 {hit:.2%}, 加速比 {speedup:.2f}x")
    base = rows[1][2]  # 5% 改动率的加速比
    lines.append(
        f"  对齐官方口径: vanilla 108 tok/s x {base:.2f} = {engine.fast_apply_tps(base):.0f} tok/s（官方约 1000 tok/s）"
    )
    lines.append(
        f"  5% 改动率下 8192 token 重写耗时 {engine.edit_wall_time_ms(8192, base):.0f} ms"
    )
    return "\n".join(lines)


def scenario_sandbox() -> str:
    requests = [
        Sandbox("agent-0", cpu=4, mem_gb=16, ttl_ticks=3),
        Sandbox("agent-1", cpu=8, mem_gb=32, ttl_ticks=2),
        Sandbox("agent-2", cpu=4, mem_gb=8, ttl_ticks=4),
        Sandbox("agent-3", cpu=16, mem_gb=64, ttl_ticks=2),  # 几乎独占整机的重任务
        Sandbox("agent-4", cpu=4, mem_gb=8, ttl_ticks=3),
    ]
    host = Host(total_cpu=32, total_mem_gb=128)
    stats = run_workload(host, requests, n_ticks=8)
    lines = [
        "场景4 后台 Agent 沙箱调度（32 核/128G 宿主机，5 个 Agent）",
        f"  统计: {stats}",
        "  事件流(前 8 条):",
    ]
    for e in host.events[:8]:
        lines.append(f"    {e}")
    return "\n".join(lines)


def scenario_economics() -> str:
    lines = ["场景5 订阅推理经济学（Pro $20/月，含 $20 API 价额度）"]
    for m in ("sonnet_4", "gemini", "gpt_4.1"):
        lines.append(
            f"  {m}: 单请求成本 ${request_cost(m):.4f}, $20 额度约 {break_even_requests(m):.0f} 次"
        )
    light = monthly_margin("sonnet_4", 100)
    heavy = monthly_margin("sonnet_4", 600)
    lines.append(f"  轻度(100 次/月): {light}")
    lines.append(f"  重度(600 次/月): {heavy}")
    lines.append(f"  Router 节省(Auto Intelligence vs 全量 Fable 5): {routing_savings():.1f}%")
    lines.append(
        f"  cost per commit 官方口径: "
        + ", ".join(f"{k} ${v}" for k, v in COST_PER_COMMIT.items())
    )
    lines.append(f"  Tab 日请求 4 亿次的推理成本教学折算: ${tab_serving_cost_day():,.0f}/天")
    return "\n".join(lines)


def run_all() -> str:
    parts = [
        scenario_indexing(),
        scenario_latency(),
        scenario_speculative(),
        scenario_sandbox(),
        scenario_economics(),
    ]
    return "\n\n".join(parts)


if __name__ == "__main__":
    print(run_all())
