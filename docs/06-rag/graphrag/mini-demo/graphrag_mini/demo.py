"""端到端演示：构建图谱 -> 三种查询模式 -> 增量更新 -> 成本对比。

运行：
    python -m graphrag_mini.demo
"""

from __future__ import annotations

from .community import (
    summarize_communities,
    summarize_super_communities,
)
from .corpus import CHUNKS, UPDATE_CHUNK, UPDATE_CHUNK_ID
from .cost import CostMeter
from .extract import extract_chunks
from .graph import KnowledgeGraph
from .query import (
    global_search,
    hybrid_search,
    local_search,
    multi_hop_search,
    vector_search,
)


def build_index(chunks: dict[str, str], meter: CostMeter | None = None):
    """索引构建流水线：抽取 -> 建图 -> 社区检测 -> 社区摘要。"""
    kg = KnowledgeGraph()
    results = extract_chunks(chunks, meter=meter)
    kg.ingest(results)
    levels = kg.detect_hierarchy()
    level0_summaries = summarize_communities(kg, levels[0], level=0, meter=meter)
    super_summaries = []
    if len(levels) > 1:
        super_summaries = summarize_super_communities(
            kg, level0_summaries, levels[1], meter=meter
        )
    return kg, results, levels, level0_summaries, super_summaries


def run_demo(verbose: bool = True) -> dict:
    stats: dict = {}
    line = lambda *a: print(*a) if verbose else None

    line("=" * 72)
    line("场景 1：索引构建（抽取 -> 建图 -> 社区检测 -> 社区摘要）")
    line("=" * 72)
    meter = CostMeter()
    kg, results, levels, level0, level1 = build_index(CHUNKS, meter=meter)
    stats["entities"] = len(kg.entities)
    stats["relations"] = kg.relation_count
    stats["level0_communities"] = len(levels[0])
    stats["level1_communities"] = len(levels[1]) if len(levels) > 1 else 0
    stats["index_cost"] = (meter.extract_calls, meter.summary_calls)
    line(f"文档: {len(CHUNKS)} 段")
    line(f"实体: {stats['entities']} 个 / 关系: {stats['relations']} 条")
    line(f"一级社区: {stats['level0_communities']} 个 / 二级社区: {stats['level1_communities']} 个")
    for idx, summary in enumerate(level0):
        line(f"  社区{idx}: {summary.text}")
        for stmt in summary.statements[:3]:
            line(f"    - {stmt}")

    line()
    line("=" * 72)
    line("场景 2：局部查询 —— “GraphRAG 是谁提出的？”")
    line("=" * 72)
    q_local = "GraphRAG 是谁提出的？"
    local = local_search(kg, q_local)
    stats["local_entities"] = local.entities
    stats["local_relations"] = [r.statement() for r in local.relations[:3]]
    line(f"命中实体: {local.entities}")
    for rel in local.relations[:4]:
        line(f"  {rel.statement()}  (来源 {sorted(rel.chunk_ids)}, 权重 {rel.weight})")
    line(f"上下文 chunk: {local.chunk_ids}")

    line()
    line("=" * 72)
    line("场景 3：全局查询 —— “围绕知识图谱的检索技术有哪些研究进展？”")
    line("=" * 72)
    q_global = "围绕知识图谱的检索技术有哪些研究进展？"
    glob = global_search(level0, q_global, top_k=2)
    stats["global_partials"] = len(glob.partials)
    for score, text in glob.partials:
        line(f"  [score={score}] {text}")

    line()
    line("=" * 72)
    line("场景 4：多跳查询 vs 向量基线")
    line("    问题：“由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？”")
    line("=" * 72)
    q_multi = "由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"
    hop = multi_hop_search(kg, q_multi)
    stats["multihop_paths"] = [" -> ".join(p) for p in hop.paths]
    stats["multihop_chunks"] = hop.chunk_ids
    line(f"种子实体: {hop.seeds}")
    for path in hop.paths[:3]:
        line(f"  路径: {' -> '.join(path)}")
    line(f"涉及 chunk: {hop.chunk_ids}（多跳答案需要跨多段拼接）")
    vec = vector_search(CHUNKS, q_multi, k=3)
    stats["vector_top"] = vec
    line("向量基线 top-3（每段只含局部信息，无法拼出完整答案链）：")
    for chunk_id, sim in vec:
        line(f"  [{sim:.3f}] {chunk_id}: {CHUNKS[chunk_id]}")

    line()
    line("=" * 72)
    line("场景 5：增量更新 —— 新文档接入已有图谱")
    line("=" * 72)
    kg2 = KnowledgeGraph()
    kg2.ingest(extract_chunks(CHUNKS))
    kg2.ingest(extract_chunks({UPDATE_CHUNK_ID: UPDATE_CHUNK}))
    q_new = "NebulaGraph 是由谁开发的，它可以存储什么？"
    local2 = local_search(kg2, q_new)
    stats["updated_relations"] = kg2.relation_count
    stats["incremental_answer"] = [r.statement() for r in local2.relations[:3]]
    line(f"更新后关系数: {kg2.relation_count}（+{kg2.relation_count - kg.relation_count}）")
    line(f"查询: {q_new}")
    for rel in local2.relations[:3]:
        line(f"  {rel.statement()}  (来源 {sorted(rel.chunk_ids)})")

    line()
    line("=" * 72)
    line("场景 6：索引成本对比 —— 预计算全部摘要 vs Lazy 式延迟计算")
    line("=" * 72)
    full_meter = CostMeter()
    build_index(CHUNKS, meter=full_meter)  # GraphRAG 风格：预计算所有层级的摘要
    lazy_meter = CostMeter()
    extract_chunks(CHUNKS, meter=lazy_meter)  # Lazy 风格：只抽取，摘要到查询时按需做
    lazy_meter.charge_summary()  # 全局查询只触发 1 个相关社区的摘要
    stats["cost_full"] = (full_meter.extract_calls, full_meter.summary_calls)
    stats["cost_lazy"] = (lazy_meter.extract_calls, lazy_meter.summary_calls)
    line(
        f"GraphRAG 风格（预计算）: 抽取 {full_meter.extract_calls} 次 + "
        f"摘要 {full_meter.summary_calls} 次 = {full_meter.total} 次模拟 LLM 调用"
    )
    line(
        f"Lazy 风格（延迟计算）: 抽取 {lazy_meter.extract_calls} 次 + "
        f"摘要 {lazy_meter.summary_calls} 次（按需）= {lazy_meter.total} 次"
    )
    line(f"按需策略本次节省摘要调用: {full_meter.summary_calls - lazy_meter.summary_calls} 次")

    line()
    line("=" * 72)
    line("场景 7：混合检索 —— 图结果与向量结果 RRF 合并")
    line("=" * 72)
    hyb = hybrid_search(kg, CHUNKS, "GraphRAG 是谁提出的？", k=5)
    stats["hybrid_top"] = hyb[0][0] if hyb else ""
    for chunk_id, score in hyb:
        line(f"  [{score:.4f}] {chunk_id}")
    line()
    return stats


if __name__ == "__main__":
    run_demo()
