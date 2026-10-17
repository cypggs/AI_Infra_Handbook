"""抽取模块测试：词典匹配、模板谓词、RELATED_TO 回退、成本计量。"""

from graphrag_mini.cost import CostMeter
from graphrag_mini.corpus import CHUNKS, UPDATE_CHUNK
from graphrag_mini.extract import (
    ENTITY_LEXICON,
    extract_chunks,
    extract_text,
    find_entities,
    match_predicate,
)


class TestFindEntities:
    def test_empty_text(self):
        assert find_entities("") == []

    def test_single_entity(self):
        assert find_entities("vLLM 很流行") == ["vLLM"]

    def test_position_order(self):
        text = "微软研究院提出了 GraphRAG"
        assert find_entities(text) == ["微软研究院", "GraphRAG"]

    def test_longest_match_wins(self):
        # "NebulaGraph 团队" 必须优先于其子串 "NebulaGraph"。
        assert find_entities("NebulaGraph 团队") == ["NebulaGraph 团队"]

    def test_lexicon_categories(self):
        assert ENTITY_LEXICON["GraphRAG"] == "PRODUCT"
        assert ENTITY_LEXICON["知识图谱"] == "CONCEPT"


class TestMatchPredicate:
    def test_developed_by(self):
        assert match_predicate("vLLM 是由伯克利开发", "vLLM", "伯克利") == "DEVELOPED_BY"

    def test_proposed_by(self):
        assert match_predicate("GraphRAG 由微软研究院提出", "GraphRAG", "微软研究院") == "PROPOSED_BY"

    def test_proposed_by_with_shi(self):
        assert match_predicate("X 是由 Y 提出的方法", "X", "Y") == "PROPOSED_BY"

    def test_inspired_by(self):
        assert match_predicate("RadixAttention 受 PagedAttention 启发", "RadixAttention", "PagedAttention") == "INSPIRED_BY"

    def test_variant_priority_over_shorter(self):
        # 长模板优先于 "{A}是{B}..." 类短模板
        assert match_predicate("LightRAG 是 GraphRAG 的轻量化改进", "LightRAG", "GraphRAG") == "VARIANT_OF"
        assert match_predicate("HippoRAG 是对 GraphRAG 的改进", "HippoRAG", "GraphRAG") == "VARIANT_OF"

    def test_core_tech(self):
        assert match_predicate("PagedAttention 是 vLLM 的核心技术", "PagedAttention", "vLLM") == "CORE_TECH_OF"

    def test_fallback_related_to(self):
        assert match_predicate("A 和 B 在同一句出现", "A", "B") == "RELATED_TO"

    def test_same_entity_returns_related(self):
        assert match_predicate(" anything ", "X", "X") == "RELATED_TO"


class TestExtractText:
    def test_c1_entities(self):
        result = extract_text(CHUNKS["C1"], chunk_id="C1")
        assert result.entities == ["vLLM", "加州大学伯克利分校", "PagedAttention"]

    def test_c1_triples(self):
        result = extract_text(CHUNKS["C1"], chunk_id="C1")
        preds = {(t.subject, t.predicate, t.object) for t in result.triples}
        assert ("vLLM", "DEVELOPED_BY", "加州大学伯克利分校") in preds
        assert ("PagedAttention", "CORE_TECH_OF", "vLLM") in preds
        assert len(result.triples) == 2

    def test_c3_inspired_by(self):
        result = extract_text(CHUNKS["C3"], chunk_id="C3")
        preds = {(t.subject, t.predicate, t.object) for t in result.triples}
        assert ("RadixAttention", "INSPIRED_BY", "PagedAttention") in preds
        assert ("RadixAttention", "CORE_TECH_OF", "SGLang") in preds

    def test_update_chunk_has_stores(self):
        result = extract_text(UPDATE_CHUNK, chunk_id="C8")
        preds = {(t.subject, t.predicate, t.object) for t in result.triples}
        assert ("NebulaGraph", "STORES", "GraphRAG") in preds
        assert ("NebulaGraph", "DEVELOPED_BY", "NebulaGraph 团队") in preds

    def test_noise_related_to(self):
        # 无模板匹配的共现对回退为 RELATED_TO（OpenIE 噪声的教学点）
        result = extract_text(UPDATE_CHUNK, chunk_id="C8")
        preds = {(t.subject, t.predicate, t.object) for t in result.triples}
        assert ("NebulaGraph", "RELATED_TO", "知识图谱") in preds

    def test_chunk_id_attached(self):
        result = extract_text(CHUNKS["C5"], chunk_id="C5")
        assert all(t.chunk_id == "C5" for t in result.triples)

    def test_deterministic(self):
        a = extract_text(CHUNKS["C6"], chunk_id="C6")
        b = extract_text(CHUNKS["C6"], chunk_id="C6")
        assert a.entities == b.entities
        assert [ (t.subject, t.predicate, t.object) for t in a.triples ] == [
            (t.subject, t.predicate, t.object) for t in b.triples
        ]


class TestExtractChunks:
    def test_counts_chunks(self):
        meter = CostMeter()
        results = extract_chunks(CHUNKS, meter=meter)
        assert len(results) == len(CHUNKS)
        assert meter.extract_calls == len(CHUNKS)

    def test_no_meter(self):
        meter = CostMeter()
        extract_chunks(CHUNKS)
        assert meter.total == 0
