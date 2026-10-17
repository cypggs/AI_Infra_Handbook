"""查询测试：向量基线、局部检索、多跳检索、全局检索、混合检索。"""

import numpy as np
import pytest

from graphrag_mini.community import summarize_communities
from graphrag_mini.corpus import CHUNKS
from graphrag_mini.extract import extract_chunks
from graphrag_mini.graph import KnowledgeGraph
from graphrag_mini.query import (
    global_search,
    hash_embedding,
    hybrid_search,
    local_search,
    match_entities,
    multi_hop_search,
    vector_search,
)


@pytest.fixture()
def kg():
    graph = KnowledgeGraph()
    graph.ingest(extract_chunks(CHUNKS))
    return graph


@pytest.fixture()
def summaries(kg):
    return summarize_communities(kg, kg.detect_communities())


class TestEmbedding:
    def test_deterministic(self):
        a = hash_embedding("GraphRAG 基于知识图谱")
        b = hash_embedding("GraphRAG 基于知识图谱")
        np.testing.assert_array_equal(a, b)

    def test_normalized(self):
        vec = hash_embedding("任意文本")
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-9

    def test_different_texts_differ(self):
        a = hash_embedding("GraphRAG 与知识图谱")
        b = hash_embedding("vLLM 与 GPU 集群")
        assert not np.allclose(a, b)

    def test_dim(self):
        assert hash_embedding("x", dim=32).shape == (32,)


class TestVectorBaseline:
    def test_top_k_sorted(self):
        scored = vector_search(CHUNKS, "GraphRAG 是谁提出的？", k=3)
        assert len(scored) == 3
        sims = [s for _, s in scored]
        assert sims == sorted(sims, reverse=True)

    def test_relevant_chunk_first(self):
        scored = vector_search(CHUNKS, "GraphRAG 是谁提出的？", k=3)
        assert scored[0][0] == "C5"

    def test_known_limitation_multihop(self, kg):
        # 多跳问题：向量 top-3 各自只含局部信息，没有一段能独立回答
        q = "由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"
        top = vector_search(CHUNKS, q, k=3)
        assert len(top) == 3
        hop = multi_hop_search(kg, q)
        # 图检索拼出的 chunk 集合不等于向量 top-3 的简单并集能覆盖的答案
        vec_chunks = {c for c, _ in top}
        assert set(hop.chunk_ids) != vec_chunks


class TestMatchEntities:
    def test_order_by_position(self):
        assert match_entities("GraphRAG 和 LightRAG 的关系") == ["GraphRAG", "LightRAG"]

    def test_no_entity(self):
        assert match_entities("今天天气怎么样") == []

    def test_full_name_required(self):
        # 子串 "伯克利" 不能命中 "加州大学伯克利分校" —— 实体链接要完整
        assert match_entities("伯克利开发的引擎") == []


class TestLocalSearch:
    def test_hits(self, kg):
        result = local_search(kg, "GraphRAG 是谁提出的？")
        assert result.entities == ["GraphRAG"]
        stmts = [r.statement() for r in result.relations]
        assert any("PROPOSED_BY" in s and "微软研究院" in s for s in stmts)

    def test_context_chunks(self, kg):
        result = local_search(kg, "GraphRAG 是谁提出的？")
        # C5/CC6 直接关系 + C7（HippoRAG 是 GraphRAG 的改进）
        assert set(result.chunk_ids) == {"C5", "C6", "C7"}

    def test_unknown_entity(self, kg):
        result = local_search(kg, "完全不相关的问题")
        assert result.entities == []
        assert result.relations == []


class TestMultiHopSearch:
    def test_seeds(self, kg):
        q = "由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"
        result = multi_hop_search(kg, q)
        assert result.seeds == ["加州大学伯克利分校", "SGLang"]

    def test_best_path_first(self, kg):
        q = "由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"
        result = multi_hop_search(kg, q)
        assert result.paths[0] == [
            "加州大学伯克利分校", "PagedAttention", "RadixAttention", "SGLang",
        ]

    def test_answer_hint(self, kg):
        q = "由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"
        result = multi_hop_search(kg, q)
        assert "RadixAttention" in result.answer_hint
        assert "SGLang" in result.answer_hint

    def test_spans_chunks(self, kg):
        q = "由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"
        result = multi_hop_search(kg, q)
        # 完整答案链横跨 C2 与 C3 两段
        assert set(result.chunk_ids) == {"C2", "C3"}

    def test_single_seed_no_paths(self, kg):
        result = multi_hop_search(kg, "GraphRAG 是什么？")
        assert result.paths == []


class TestGlobalSearch:
    def test_relevant_community_first(self, kg, summaries):
        q = "围绕知识图谱的检索技术有哪些研究进展？"
        result = global_search(summaries, q, top_k=2)
        assert result.partials[0][0] == 1  # 命中 "知识图谱" 的社区排第一
        assert "GraphRAG" in result.answer

    def test_partials_count(self, kg, summaries):
        result = global_search(summaries, "无关问题", top_k=2)
        assert len(result.partials) == 2
        assert result.partials[0][0] == 0


class TestHybridSearch:
    def test_rrf_merges_both_sources(self, kg):
        ranked = hybrid_search(kg, CHUNKS, "GraphRAG 是谁提出的？", k=5)
        assert ranked[0][0] == "C5"
        chunk_ids = {c for c, _ in ranked}
        # 图的上下文 C6 与向量结果都被纳入
        assert "C6" in chunk_ids
        assert len(ranked) == 5

    def test_scores_descending(self, kg):
        ranked = hybrid_search(kg, CHUNKS, "GraphRAG 是谁提出的？", k=5)
        scores = [s for _, s in ranked]
        assert scores == sorted(scores, reverse=True)
