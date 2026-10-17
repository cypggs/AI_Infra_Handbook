"""caching 模块测试。"""

from perplexity_case_mini import caching
from perplexity_case_mini.demo import scenario_caching


def test_normalize():
    assert caching.normalize("  Hello   World ") == "hello world"
    assert caching.normalize("A  B") == caching.normalize("a b")


def test_exact_hit_after_put():
    cache = caching.AnswerCache()
    cache.put("什么是 RAG", "answer-1", now=0.0)
    answer, layer = cache.get("什么是 RAG", now=10.0)
    assert answer == "answer-1"
    assert layer == "exact"


def test_ttl_expiry():
    cache = caching.AnswerCache(ttl_s=100.0)
    cache.put("q", "a", now=0.0)
    assert cache.get("q", now=99.0)[1] == "exact"
    assert cache.get("q", now=101.0) == (None, "miss")


def test_semantic_hit_above_threshold():
    cache = caching.AnswerCache(semantic_threshold=0.85)
    cache.put("vllm pagedattention 分页 注意力 原理", "a", now=0.0)
    answer, layer = cache.get("vllm pagedattention 分页 注意力 原理 解释", now=1.0)
    assert answer == "a"
    assert layer == "semantic"


def test_semantic_miss_below_threshold():
    cache = caching.AnswerCache(semantic_threshold=0.95)
    cache.put("vllm pagedattention 分页 注意力 原理", "a", now=0.0)
    assert cache.get("vllm pagedattention 分页 注意力 原理 解释",
                     now=1.0) == (None, "miss")


def test_cosine_identical_and_disjoint():
    v = caching.query_vector("rag 检索 质量")
    assert abs(caching.cosine(v, dict(v)) - 1.0) < 1e-9
    assert caching.cosine(v, caching.query_vector("完全 无关 的 查询")) == 0.0


def test_empty_vector_cosine_zero():
    assert caching.cosine({}, {"a": 1.0}) == 0.0
    assert caching.cosine({"a": 1.0}, {}) == 0.0


def test_simulate_traffic_cost_consistency():
    stream = [("q1", 0.0), ("q1", 1.0), ("q2", 2.0), ("q2", 3.0)]
    r = caching.simulate_traffic(stream, answer_cost=0.01, ttl_s=10.0)
    assert r["n_miss"] == 2
    assert r["n_exact"] == 2
    assert abs(r["cost_usd"] - 0.02) < 1e-9
    assert abs(r["savings_pct"] - 50.0) < 1e-9


def test_simulate_savings_bounded():
    stream = [(f"query-{i}", float(i)) for i in range(50)]
    r = caching.simulate_traffic(stream, answer_cost=0.004)
    assert -0.01 <= r["savings_pct"] <= 100.0
    assert abs(r["baseline_cost_usd"] - 50 * 0.004) < 1e-9


def test_scenario_caching_exact_numbers():
    r = scenario_caching()
    assert r["n_queries"] == 600
    assert r["n_exact"] == 414
    assert r["n_semantic"] == 180
    assert r["n_miss"] == 6
    assert abs(r["total_hit_rate"] - 0.99) < 1e-9
    assert abs(r["savings_pct"] - 99.0) < 0.01
