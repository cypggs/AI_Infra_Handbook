from kv_cache_mini.tier import TieredCache, TierSpec


def make_cache(**overrides):
    params = dict(
        gpu=TierSpec("gpu", capacity_blocks=2, read_cost_per_block=0.0001,
                     write_cost_per_block=0.0002),
        cpu=TierSpec("cpu", capacity_blocks=4, read_cost_per_block=0.002,
                     write_cost_per_block=0.002),
        ssd=TierSpec("ssd", capacity_blocks=8, read_cost_per_block=0.02,
                     write_cost_per_block=0.02),
        prefill_cost_per_block=0.05,
    )
    params.update(overrides)
    return TieredCache(**params)


class TestTieredBasics:
    def test_put_places_in_gpu(self):
        cache = make_cache()
        cache.put("k")
        assert cache.occupancy()["gpu"] == 1

    def test_put_existing_key_is_noop(self):
        cache = make_cache()
        cache.put("k")
        cost = cache.put("k")
        assert cost == 0.0
        assert cache.occupancy()["gpu"] == 1

    def test_gpu_hit(self):
        cache = make_cache()
        cache.put("k")
        hit, tier, cost = cache.get("k")
        assert hit and tier == "gpu"
        assert cost == 0.0001

    def test_miss_returns_none(self):
        cache = make_cache()
        hit, tier, cost = cache.get("nope")
        assert not hit and tier is None and cost == 0.0

    def test_gpu_eviction_demotes_to_cpu(self):
        cache = make_cache()
        cache.put("a")
        cache.put("b")
        cache.put("c")  # 挤出 gpu 的 LRU
        occ = cache.occupancy()
        assert occ["gpu"] == 2
        assert occ["cpu"] == 1
        assert cache.demotions["gpu->cpu"] == 1

    def test_cascade_to_ssd_when_cpu_full(self):
        cache = make_cache(gpu=TierSpec("gpu", 1, 0.0001, 0.0002),
                           cpu=TierSpec("cpu", 1, 0.002, 0.002),
                           ssd=TierSpec("ssd", 8, 0.02, 0.02))
        for key in ["a", "b", "c", "d"]:
            cache.put(key)
        occ = cache.occupancy()
        assert occ["gpu"] == 1 and occ["cpu"] == 1
        assert occ["ssd"] == 2
        assert cache.demotions["cpu->ssd"] >= 1

    def test_ssd_eviction_drops(self):
        cache = make_cache(gpu=TierSpec("gpu", 1, 0.0001, 0.0002),
                           cpu=TierSpec("cpu", 1, 0.002, 0.002),
                           ssd=TierSpec("ssd", 1, 0.02, 0.02))
        for key in ["a", "b", "c", "d"]:
            cache.put(key)
        assert cache.demotions["ssd->drop"] == 1


class TestTieredPromotion:
    def test_cpu_hit_promotes_to_gpu(self):
        cache = make_cache()
        cache.put("a")
        cache.put("b")
        cache.put("c")          # a 被降级到 cpu
        hit, tier, _ = cache.get("a")
        assert hit and tier == "cpu"
        assert cache.occupancy()["gpu"] == 2
        assert "a" not in cache._data["cpu"]

    def test_promotion_cost_includes_write(self):
        cache = make_cache()
        cache.put("a")
        cache.put("b")
        cache.put("c")
        _, _, cost = cache.get("a")  # cpu hit + gpu write
        assert cost == 0.002 + 0.0002

    def test_no_promote_when_disabled(self):
        cache = make_cache()
        cache.put("a")
        cache.put("b")
        cache.put("c")
        hit, tier, cost = cache.get("a", promote=False)
        assert hit and tier == "cpu"
        assert cost == 0.002
        assert cache.occupancy()["cpu"] == 1

    def test_hit_rate_and_savings_positive(self):
        cache = make_cache()
        for key in ["x", "y", "z"]:
            cache.put(key)
        for _ in range(3):
            for key in ["x", "y", "z"]:
                cache.get(key)
        assert cache.hit_rate == 1.0
        assert cache.savings_s > 0

    def test_misses_raise_baseline(self):
        cache = make_cache()
        cache.get("a")
        cache.get("b")
        assert cache.misses == 2
        assert cache.baseline_cost_s == 0.1
        # 全 miss：缓存本身不产生迁移成本，收益为 0（既不赚也不亏）
        assert cache.total_cost_s == 0.0
        assert cache.savings_s == 0.0
