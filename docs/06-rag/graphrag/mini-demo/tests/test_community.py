"""社区摘要测试：map-reduce 结构、层次聚合、成本计量。"""

import pytest

from graphrag_mini.community import (
    summarize_communities,
    summarize_community,
    summarize_super_communities,
)
from graphrag_mini.corpus import CHUNKS
from graphrag_mini.cost import CostMeter
from graphrag_mini.extract import extract_chunks
from graphrag_mini.graph import KnowledgeGraph


@pytest.fixture()
def kg():
    graph = KnowledgeGraph()
    graph.ingest(extract_chunks(CHUNKS))
    return graph


@pytest.fixture()
def level0(kg):
    return kg.detect_communities()


class TestSummarizeCommunity:
    def test_text_contains_core_entities(self, kg, level0):
        rag_community = next(c for c in level0 if "GraphRAG" in c)
        summary = summarize_community(kg, rag_community)
        assert "GraphRAG" in summary.text
        assert "核心实体" in summary.text
        names = [n for n, _ in summary.top_entities]
        assert "GraphRAG" in names
        assert "知识图谱" in names

    def test_statements_are_relations(self, kg, level0):
        rag_community = next(c for c in level0 if "GraphRAG" in c)
        summary = summarize_community(kg, rag_community)
        assert len(summary.statements) > 0
        assert all("-[" in s and "]->" in s for s in summary.statements)
        assert any("PROPOSED_BY" in s for s in summary.statements)

    def test_relation_histogram(self, kg, level0):
        rag_community = next(c for c in level0 if "GraphRAG" in c)
        summary = summarize_community(kg, rag_community)
        hist = dict(summary.relation_hist)
        assert hist["PROPOSED_BY"] == 3  # GraphRAG/LightRAG/HippoRAG 各一条
        assert hist["VARIANT_OF"] == 2

    def test_empty_community(self, kg):
        summary = summarize_community(kg, ["不存在的实体"])
        assert summary.statements == []
        assert "（空）" in summary.text

    def test_deterministic(self, kg, level0):
        rag_community = next(c for c in level0 if "GraphRAG" in c)
        a = summarize_community(kg, rag_community)
        b = summarize_community(kg, rag_community)
        assert a.text == b.text
        assert a.statements == b.statements


class TestSummarizeCommunities:
    def test_batch_with_meter(self, kg, level0):
        meter = CostMeter()
        summaries = summarize_communities(kg, level0, meter=meter)
        assert len(summaries) == 3
        assert meter.summary_calls == 3

    def test_source_community_index(self, kg, level0):
        summaries = summarize_communities(kg, level0)
        for idx, s in enumerate(summaries):
            assert s.source_communities == [idx]
            assert s.level == 0


class TestSuperCommunities:
    def test_super_summary_aggregates_members(self, kg, level0):
        summaries = summarize_communities(kg, level0)
        # 把三个一级社区合成一个超级社区
        super_summaries = summarize_super_communities(
            kg, summaries, [[0, 1, 2]]
        )
        assert len(super_summaries) == 1
        super_summary = super_summaries[0]
        assert super_summary.level == 1
        assert super_summary.source_communities == [0, 1, 2]
        assert len(super_summary.members) == 20  # 全部实体

    def test_super_summary_meter(self, kg, level0):
        summaries = summarize_communities(kg, level0)
        meter = CostMeter()
        summarize_super_communities(kg, summaries, [[0], [1, 2]], meter=meter)
        assert meter.summary_calls == 2

    def test_super_summary_statements_traceable(self, kg, level0):
        summaries = summarize_communities(kg, level0)
        super_summary = summarize_super_communities(kg, summaries, [[2]])[0]
        assert any("GraphRAG" in s for s in super_summary.statements)
