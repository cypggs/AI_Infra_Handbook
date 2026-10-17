"""端到端演示测试：统计数字、场景输出、成本对比、确定性。"""

from graphrag_mini.demo import build_index, run_demo
from graphrag_mini.corpus import CHUNKS, UPDATE_CHUNK, UPDATE_CHUNK_ID
from graphrag_mini.cost import CostMeter
from graphrag_mini.extract import extract_chunks
from graphrag_mini.graph import KnowledgeGraph


class TestBuildIndex:
    def test_stats(self):
        meter = CostMeter()
        kg, results, levels, level0, level1 = build_index(CHUNKS, meter=meter)
        assert len(kg.entities) == 20
        assert kg.relation_count == 22
        assert len(levels[0]) == 3
        assert len(level0) == 3
        assert len(level1) == 3
        # 7 段语料：7 次抽取 + 3 个一级摘要 + 3 个二级摘要
        assert (meter.extract_calls, meter.summary_calls) == (7, 6)

    def test_incremental_then_query(self):
        kg = KnowledgeGraph()
        kg.ingest(extract_chunks(CHUNKS))
        kg.ingest(extract_chunks({UPDATE_CHUNK_ID: UPDATE_CHUNK}))
        assert kg.relation_count == 26
        assert "NebulaGraph" in kg.neighbors("GraphRAG")


class TestRunDemo:
    def test_stats(self):
        stats = run_demo(verbose=False)
        assert stats["entities"] == 20
        assert stats["relations"] == 22
        assert stats["level0_communities"] == 3
        assert stats["level1_communities"] == 3
        assert stats["cost_full"] == (7, 6)
        assert stats["cost_lazy"] == (7, 1)
        assert stats["updated_relations"] == 26

    def test_local_scenario(self):
        stats = run_demo(verbose=False)
        assert stats["local_entities"] == ["GraphRAG"]
        assert any("微软研究院" in s for s in stats["local_relations"])

    def test_multihop_scenario(self):
        stats = run_demo(verbose=False)
        assert stats["multihop_paths"][0] == (
            "加州大学伯克利分校 -> PagedAttention -> RadixAttention -> SGLang"
        )
        assert set(stats["multihop_chunks"]) == {"C2", "C3"}
        # 向量基线返回的是各自含局部信息的 chunk
        assert len(stats["vector_top"]) == 3

    def test_incremental_scenario(self):
        stats = run_demo(verbose=False)
        assert any("STORES" in s for s in stats["incremental_answer"])
        assert any("DEVELOPED_BY" in s for s in stats["incremental_answer"])

    def test_hybrid_scenario(self):
        stats = run_demo(verbose=False)
        assert stats["hybrid_top"] == "C5"

    def test_deterministic(self):
        a = run_demo(verbose=False)
        b = run_demo(verbose=False)
        assert a == b
