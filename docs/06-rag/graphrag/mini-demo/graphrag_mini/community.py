"""社区摘要：map-reduce 结构的确定性模拟。

GraphRAG 的核心创新是 "预计算社区摘要"：对每个社区，LLM 先 map
（逐条关系生成描述），再 reduce（汇总成一段社区报告）。查询时的全局
检索就是对社区报告再做一次 map-reduce。

本模块用纯聚合统计模拟这一过程：
- map：把社区内每条关系变成一条陈述语句；
- reduce：统计高频实体 / 谓词分布，拼出确定性的摘要文本。

这样摘要内容完全可测试，同时保留了 "map-reduce 两阶段" 的结构。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .cost import CostMeter
from .graph import KnowledgeGraph, Relation


@dataclass
class CommunitySummary:
    """一个社区的确定性摘要。"""

    members: list[str]
    statements: list[str]                      # map 阶段输出：逐条关系陈述
    top_entities: list[tuple[str, int]]        # reduce 阶段：实体频次
    relation_hist: list[tuple[str, int]]       # reduce 阶段：谓词直方图
    text: str                                  # 汇总后的社区报告文本
    level: int = 0
    source_communities: list[int] = field(default_factory=list)


def _summarize_members(
    kg: KnowledgeGraph,
    members: list[str],
    member_set: set[str],
    level: int,
    source_communities: list[int],
    max_entities: int,
    max_statements: int,
) -> CommunitySummary:
    rels: list[Relation] = [
        rel
        for rel in kg.relations.values()
        if rel.subject in member_set and rel.object in member_set
    ]
    rels.sort(key=lambda r: (-r.weight, r.statement()))

    entity_counter: Counter[str] = Counter()
    for rel in rels:
        entity_counter[rel.subject] += rel.weight
        entity_counter[rel.object] += rel.weight
    top_entities = sorted(
        entity_counter.items(), key=lambda kv: (-kv[1], kv[0])
    )[:max_entities]

    relation_hist = sorted(
        Counter(rel.predicate for rel in rels).items(),
        key=lambda kv: (-kv[1], kv[0]),
    )

    statements = [rel.statement() for rel in rels[:max_statements]]

    core = "、".join(name for name, _ in top_entities) if top_entities else "（空）"
    text = (
        f"[level {level} 社区] 成员 {len(members)} 个实体，内部关系 {len(rels)} 条；"
        f"核心实体：{core}；"
        f"主要关系类型：{relation_hist[0][0] if relation_hist else '（无）'}。"
    )
    return CommunitySummary(
        members=members,
        statements=statements,
        top_entities=top_entities,
        relation_hist=relation_hist,
        text=text,
        level=level,
        source_communities=source_communities,
    )


def summarize_community(
    kg: KnowledgeGraph,
    members: list[str],
    level: int = 0,
    source_communities: list[int] | None = None,
    max_entities: int = 4,
    max_statements: int = 6,
) -> CommunitySummary:
    """对单个社区生成确定性摘要（模拟一次 LLM 摘要调用）。"""
    return _summarize_members(
        kg,
        sorted(members),
        set(members),
        level,
        source_communities or [],
        max_entities,
        max_statements,
    )


def summarize_communities(
    kg: KnowledgeGraph,
    communities: list[list[str]],
    level: int = 0,
    meter: CostMeter | None = None,
) -> list[CommunitySummary]:
    """对一层社区批量生成摘要；每个社区计 1 次模拟 LLM 调用。"""
    summaries = []
    for idx, members in enumerate(communities):
        if meter is not None:
            meter.charge_summary()
        summaries.append(
            summarize_community(
                kg, members, level=level, source_communities=[idx]
            )
        )
    return summaries


def summarize_super_communities(
    kg: KnowledgeGraph,
    level0_summaries: list[CommunitySummary],
    level1_groups: list[list[int]],
    meter: CostMeter | None = None,
) -> list[CommunitySummary]:
    """用一级摘要聚合出二级（超级社区）摘要。

    这是 GraphRAG 层次化社区报告的缩影：上级报告不是重新读原文，
    而是对下级报告做二次 reduce。
    """
    summaries = []
    for group in level1_groups:
        if meter is not None:
            meter.charge_summary()
        members: list[str] = []
        statements: list[str] = []
        for idx in group:
            members.extend(level0_summaries[idx].members)
            statements.extend(level0_summaries[idx].statements)
        merged = summarize_community(
            kg,
            sorted(set(members)),
            level=1,
            source_communities=list(group),
            max_entities=6,
            max_statements=10,
        )
        # 超级社区的 statements 取各子社区的代表性陈述，保证内容可追溯。
        merged.statements = sorted(set(statements))[:10]
        summaries.append(merged)
    return summaries
