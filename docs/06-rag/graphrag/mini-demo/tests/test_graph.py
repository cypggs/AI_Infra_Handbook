"""图存储与社区检测测试：合并、邻接、标签传播、层次化、寻路。"""

import pytest

from graphrag_mini.corpus import CHUNKS, UPDATE_CHUNK, UPDATE_CHUNK_ID
from graphrag_mini.extract import Triple, extract_chunks, extract_text
from graphrag_mini.graph import KnowledgeGraph


@pytest.fixture()
def kg():
    graph = KnowledgeGraph()
    graph.ingest(extract_chunks(CHUNKS))
    return graph


def _triangle(kg, prefix):
    a, b, c = f"{prefix}a", f"{prefix}b", f"{prefix}c"
    for s, o in [(a, b), (b, c), (a, c)]:
        kg.add_triple(Triple(s, "LINK", o, chunk_id="T"))


class TestBuild:
    def test_corpus_stats(self, kg):
        assert len(kg) == 20
        assert kg.relation_count == 22

    def test_triple_merge_accumulates_weight(self):
        graph = KnowledgeGraph()
        graph.add_triple(Triple("A", "X", "B", chunk_id="c1"))
        graph.add_triple(Triple("A", "X", "B", chunk_id="c2"))
        rel = graph.relations[("A", "X", "B")]
        assert rel.weight == 2
        assert rel.chunk_ids == {"c1", "c2"}
        assert graph.relation_count == 1

    def test_adjacency_bidirectional(self):
        graph = KnowledgeGraph()
        graph.add_triple(Triple("A", "X", "B"))
        assert graph.neighbors("A") == {"B"}
        assert graph.neighbors("B") == {"A"}

    def test_degree(self, kg):
        # GraphRAG: 微软研究院/知识图谱/检索增强生成/社区摘要/LightRAG/HippoRAG
        assert kg.degree("GraphRAG") == 6

    def test_relations_of_sorted_by_weight(self):
        graph = KnowledgeGraph()
        graph.add_triple(Triple("A", "X", "B", chunk_id="c1"))
        graph.add_triple(Triple("A", "Y", "C", chunk_id="c1"))
        graph.add_triple(Triple("A", "Z", "D", chunk_id="c1"))
        graph.add_triple(Triple("A", "Y", "C", chunk_id="c2"))
        rels = graph.relations_of("A")
        assert rels[0].predicate == "Y"  # weight 2 排第一


class TestCommunities:
    def test_two_triangles(self):
        graph = KnowledgeGraph()
        _triangle(graph, "t1")
        _triangle(graph, "t2")
        communities = graph.detect_communities()
        assert len(communities) == 2
        sizes = sorted(len(c) for c in communities)
        assert sizes == [3, 3]

    def test_isolated_node_own_community(self):
        graph = KnowledgeGraph()
        _triangle(graph, "t1")
        graph.add_triple(Triple("lonely", "X", "node0", chunk_id="T"))
        communities = graph.detect_communities()
        assert len(communities) == 2

    def test_corpus_communities(self, kg):
        communities = {frozenset(c) for c in kg.detect_communities()}
        expected = {
            frozenset({"vLLM", "PagedAttention", "RadixAttention", "SGLang",
                       "加州大学伯克利分校", "GPU 集群", "LLM 推理社区"}),
            frozenset({"Kubernetes", "Google", "KServe"}),
            frozenset({"GraphRAG", "LightRAG", "HippoRAG", "微软研究院",
                       "香港大学数据科学实验室", "俄亥俄州立大学", "知识图谱",
                       "社区摘要", "个性化 PageRank", "检索增强生成"}),
        }
        assert communities == expected

    def test_deterministic(self, kg):
        assert kg.detect_communities() == kg.detect_communities()

    def test_hierarchy_two_levels(self, kg):
        levels = kg.detect_hierarchy()
        assert len(levels) == 2
        assert len(levels[0]) == 3
        assert len(levels[1]) == 3  # 三个社区互不连通，上层各自成组
        # level1 的元素是 level0 社区的下标分组
        assert sorted(i for g in levels[1] for i in g) == [0, 1, 2]


class TestPaths:
    def test_direct_edge(self, kg):
        paths = kg.find_paths("vLLM", "加州大学伯克利分校", max_depth=2)
        assert ["vLLM", "加州大学伯克利分校"] in paths

    def test_multi_hop_path_found(self, kg):
        paths = kg.find_paths("加州大学伯克利分校", "SGLang", max_depth=4)
        assert ["加州大学伯克利分校", "PagedAttention", "RadixAttention", "SGLang"] in paths

    def test_no_path_within_depth(self, kg):
        # GraphRAG 与 vLLM 不连通，任意深度都找不到
        assert kg.find_paths("GraphRAG", "vLLM", max_depth=4) == []

    def test_path_respects_max_depth(self, kg):
        # 1 跳内不可能从伯克利到 SGLang（最近的合法路径是 3 跳）
        assert kg.find_paths("加州大学伯克利分校", "SGLang", max_depth=1) == []

    def test_missing_node(self, kg):
        assert kg.find_paths("不存在的实体", "SGLang") == []


class TestIncremental:
    def test_update_grows_graph(self, kg):
        before = kg.relation_count
        kg.ingest(extract_chunks({UPDATE_CHUNK_ID: UPDATE_CHUNK}))
        assert kg.relation_count == before + 4
        assert kg.degree("NebulaGraph") == 3  # 团队 / 知识图谱 / GraphRAG
        assert "NebulaGraph" in kg.neighbors("GraphRAG")
