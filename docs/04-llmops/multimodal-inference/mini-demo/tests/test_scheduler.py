from multimodal_inference_mini.scheduler import (
    QWEN_MAX_PIXELS,
    QWEN_MIN_PIXELS,
    MultimodalScheduler,
    Request,
    StageCost,
    resolution_sweep,
    visual_token_count,
)


class TestVisualTokenCount:
    def test_small_image_is_upscaled_to_floor(self):
        # 224x224 = 50176 px < min_pixels(200704): upscaled to floor
        assert visual_token_count(224, 224) == QWEN_MIN_PIXELS // (28 * 28)

    def test_medium_image_scales_with_pixels(self):
        # 896x896 = 802816 px, inside range: tokens = 32*32
        assert visual_token_count(896, 896) == 1024

    def test_huge_image_is_clamped_near_cap(self):
        # 7680x4320 >> max_pixels: clamped, with a small floor-rounding loss
        tokens = visual_token_count(7680, 4320)
        assert tokens <= QWEN_MAX_PIXELS // (28 * 28)
        assert tokens >= QWEN_MAX_PIXELS // (28 * 28) - 100

    def test_clamp_bounds_respected(self):
        for w, h in [(1, 1), (64, 64), (512, 512), (2000, 2000), (10000, 10000)]:
            tokens = visual_token_count(w, h)
            assert QWEN_MIN_PIXELS // 784 <= tokens <= QWEN_MAX_PIXELS // 784

    def test_monotonic_with_resolution(self):
        counts = [visual_token_count(s, s) for s in (224, 448, 896, 1568, 4032)]
        assert counts == sorted(counts)
        # clamping pins both ends: small images share the floor, huge ones the cap
        assert counts[0] == counts[1] == QWEN_MIN_PIXELS // (28 * 28)

    def test_zero_size_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            visual_token_count(0, 100)

    def test_resolution_sweep_shape(self):
        out = resolution_sweep([(224, 224), (896, 896)])
        assert [o[:2] for o in out] == [(224, 224), (896, 896)]
        assert all(isinstance(o[2], int) and o[2] > 0 for o in out)


class TestRequest:
    def test_text_only_has_zero_visual(self):
        r = Request("a", 200)
        assert r.visual_tokens() == 0

    def test_multi_image_adds_up(self):
        one = visual_token_count(896, 896)
        r = Request("a", 10, images=((896, 896), (896, 896)))
        assert r.visual_tokens() == 2 * one


class TestScheduler:
    def test_text_only_prefill_linear(self):
        sch = MultimodalScheduler()
        reqs = [Request(f"t{i}", 100) for i in range(4)]
        res = sch.schedule(reqs)
        assert res.llm_prefill_ms == 400 * sch.cost.llm_ms_per_token
        assert res.encoder_ms == sch.cost.encoder_ms_per_patch
        assert res.n_images == 0

    def test_mixed_batch_counts_both(self):
        sch = MultimodalScheduler()
        reqs = [Request(f"m{i}", 100, images=((896, 896),)) for i in range(4)]
        res = sch.schedule(reqs)
        assert res.visual_tokens == 4 * 1024
        assert res.llm_prefill_ms == (400 + 4096) * sch.cost.llm_ms_per_token
        assert res.n_images == 4

    def test_encoder_patches_are_4x_tokens(self):
        sch = MultimodalScheduler()
        r = Request("a", 0, images=((896, 896),))
        assert sch.encoder_patches(r) == 4 * visual_token_count(896, 896)

    def test_overlap_makespan_is_max(self):
        cost = StageCost(llm_ms_per_token=0.05, encoder_ms_per_patch=0.02,
                         encoder_batch_patch_per_ms=64.0)
        sch = MultimodalScheduler(cost)
        res = sch.schedule([Request("a", 100, images=((896, 896),)) for _ in range(8)])
        assert res.makespan_ms == max(res.llm_prefill_ms, res.encoder_ms)
        assert res.serial_ms == res.llm_prefill_ms + res.encoder_ms

    def test_no_overlap_makespan_is_sum(self):
        cost = StageCost(llm_ms_per_token=0.05)
        sch = MultimodalScheduler(cost, overlap=False)
        res = sch.schedule([Request("a", 100, images=((896, 896),))])
        assert res.makespan_ms == res.serial_ms

    def test_compare_slowdown_and_share(self):
        sch = MultimodalScheduler()
        r = sch.compare_mixed_vs_text(4, 200, (3024, 4032))
        assert r["prefill_slowdown"] > 1
        assert 0 < r["visual_share"] < 1
        assert r["mixed"].visual_tokens > 0
        assert r["text_only"].visual_tokens == 0

    def test_text_only_baseline_excludes_images(self):
        sch = MultimodalScheduler()
        res = sch.schedule([Request("a", 300, images=((896, 896),))])
        assert res.text_only_baseline_ms == 300 * sch.cost.llm_ms_per_token
