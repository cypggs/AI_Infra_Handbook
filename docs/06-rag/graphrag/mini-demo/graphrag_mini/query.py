"""查询：局部检索 / 全局检索 / 多跳遍历，以及与暴力向量基线的对比。

GraphRAG 家族的查询分三类：
- local（局部）：围绕问题中的实体，沿图取一跳/两跳邻域 + 原文 chunk；
- global（全局）：对所有社区摘要做 map-reduce，回答 "语料库整体" 类问题；
- 多跳（multi-hop）：以问题中的实体为种子在图上寻路，把分散在多个
  chunk 中的事实串联起来。

本模块同时实现一个 "确定性哈希向量 + 暴力余弦" 的向量检索基线，
用于演示纯向量检索在多跳问题上为什么失败。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from .community import CommunitySummary
from .extract import ENTITY_LEXICON, find_entities
from .graph import KnowledgeGraph, Relation

EMB_DIM = 64


# --------------------------------------------------------------------------- #
# 确定性哈希向量（模拟 Embedding）
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[str]:
    """字符 unigram + bigram 分词（去空白），中文 demo 足够。"""
    chars = [c for c in text if not c.isspace()]
    tokens = list(chars)
    tokens.extend(a + b for a, b in zip(chars, chars[1:]))
    return tokens


def hash_embedding(text: str, dim: int = EMB_DIM) -> np.ndarray:
    """把文本映射为确定性的 L2 归一化向量（哈希技巧，替代真实 Embedding）。"""
    vec = np.zeros(dim, dtype=np.float64)
    for token in _tokens(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def vector_search(
    chunks: dict[str, str], query: str, k: int = 3
) -> list[tuple[str, float]]:
    """暴力向量基线：对全部 chunk 算余弦相似度，返回 top-k。"""
    q = hash_embedding(query)
    scored = []
    for chunk_id in sorted(chunks):
        sim = float(np.dot(q, hash_embedding(chunks[chunk_id])))
        scored.append((chunk_id, sim))
    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    return scored[:k]


# --------------------------------------------------------------------------- #
# 查询结果数据结构
# --------------------------------------------------------------------------- #
@dataclass
class LocalResult:
    entities: list[str]
    relations: list[Relation]
    chunk_ids: list[str]


@dataclass
class MultiHopResult:
    seeds: list[str]
    paths: list[list[str]]            # 找到的多跳路径（实体链）
    relations: list[Relation]         # 路径上的关系
    chunk_ids: list[str]
    answer_hint: str                  # 由路径推导出的答案提示


@dataclass
class GlobalResult:
    query: str
    partials: list[tuple[int, str]]   # (score, 社区摘要文本)
    answer: str


# --------------------------------------------------------------------------- #
# 局部检索
# --------------------------------------------------------------------------- #
def match_entities(query: str) -> list[str]:
    """在问题中匹配实体，按出现位置排序。"""
    found = find_entities(query)
    return found


def local_search(
    kg: KnowledgeGraph, query: str, max_relations: int = 6
) -> LocalResult:
    """局部检索：从问题实体出发取一跳邻域，按边权排序返回。"""
    entities = match_entities(query)
    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for entity in entities:
        for rel in kg.relations_of(entity):
            if rel.key() in seen:
                continue
            seen.add(rel.key())
            relations.append(rel)
    relations.sort(key=lambda r: (-r.weight, r.statement()))
    relations = relations[:max_relations]

    chunk_ids: set[str] = set()
    for rel in relations:
        chunk_ids.update(rel.chunk_ids)
    for entity in entities:
        chunk_ids.update(kg.entities.get(entity, {}).get("chunk_ids", set()))
    return LocalResult(
        entities=entities,
        relations=relations,
        chunk_ids=sorted(chunk_ids),
    )


# --------------------------------------------------------------------------- #
# 多跳检索
# --------------------------------------------------------------------------- #
def multi_hop_search(
    kg: KnowledgeGraph, query: str, max_depth: int = 4
) -> MultiHopResult:
    """以问题中的实体为种子寻路，把分散事实串成实体链。"""
    seeds = match_entities(query)
    paths: list[list[str]] = []
    # 依次尝试所有 (种子, 种子) 有序对，取最先找到的最短路径。
    for i, start in enumerate(seeds):
        for goal in seeds[i + 1 :]:
            found = kg.find_paths(start, goal, max_depth=max_depth)
            if found:
                paths.extend(found[:2])
                break
        if paths:
            break
    paths.sort(
        key=lambda p: (
            sum(
                1
                for a, b in zip(p, p[1:])
                if all(
                    rel.predicate == "RELATED_TO"
                    for rel in kg.relations.values()
                    if {rel.subject, rel.object} == {a, b}
                )
            ),
            len(p),
            p,
        )
    )
    paths = paths[:3]

    # 收集路径上的关系（任意相邻节点之间的所有关系）。
    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for path in paths:
        for a, b in zip(path, path[1:]):
            for rel in kg.relations.values():
                if {rel.subject, rel.object} == {a, b} and rel.key() not in seen:
                    seen.add(rel.key())
                    relations.append(rel)
    relations.sort(key=lambda r: (-r.weight, r.statement()))

    chunk_ids: set[str] = set()
    for rel in relations:
        chunk_ids.update(rel.chunk_ids)

    hint = ""
    if paths:
        hint = " -> ".join(paths[0])
    return MultiHopResult(
        seeds=seeds,
        paths=paths,
        relations=relations,
        chunk_ids=sorted(chunk_ids),
        answer_hint=hint,
    )


# --------------------------------------------------------------------------- #
# 全局检索：对社区摘要做 map-reduce
# --------------------------------------------------------------------------- #
def global_search(
    summaries: list[CommunitySummary],
    query: str,
    top_k: int = 2,
) -> GlobalResult:
    """map：每个社区摘要按问题中的实体命中数打分；reduce：合并 top-k 摘要。"""
    query_entities = set(match_entities(query))
    scored: list[tuple[int, int, str]] = []
    for idx, summary in enumerate(summaries):
        text = summary.text + " " + " ".join(summary.statements)
        score = sum(1 for e in query_entities if e in text)
        scored.append((score, -idx, summary.text + " " + "；".join(summary.statements[:3])))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    partials = [(s, text) for s, _, text in scored[:top_k]]
    answer = "\n".join(text for _, text in partials)
    return GlobalResult(query=query, partials=partials, answer=answer)


# --------------------------------------------------------------------------- #
# 混合检索：图局部结果与向量结果按 RRF 合并
# --------------------------------------------------------------------------- #
def hybrid_search(
    kg: KnowledgeGraph,
    chunks: dict[str, str],
    query: str,
    k: int = 5,
) -> list[tuple[str, float]]:
    """RRF（Reciprocal Rank Fusion）合并图检索与向量检索的 chunk 排名。"""
    local = local_search(kg, query)
    vec = vector_search(chunks, query, k=k)
    scores: dict[str, float] = {}
    for rank, chunk_id in enumerate(local.chunk_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (60 + rank + 1)
    for rank, (chunk_id, _) in enumerate(vec):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (60 + rank + 1)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:k]
