"""End-to-end scenarios for the multimodal & speech inference mini demo.

Run with: python -m multimodal_inference_mini.demo
"""

from __future__ import annotations

from .codec import ENCODEC_1_5K, ENCODEC_6K, MIMI, compare_codecs, kv_growth_per_minute
from .duplex import DuplexSession, Event
from .scheduler import MultimodalScheduler, Request, resolution_sweep
from .voice import (
    DEFAULT_CONFIG,
    budget_headroom,
    first_audio_breakdown,
    interrupt_response_latency,
    optimization_table,
)


def scenario_1_resolution_sweep() -> None:
    print("=" * 70)
    print("场景 1：图片分辨率 -> 视觉 token 数 -> prefill 成本")
    print("=" * 70)
    sizes = [
        (224, 224),      # 缩略图
        (448, 448),      # 小图
        (896, 896),      # 文档截图
        (1568, 1568),    # 高清图
        (3024, 4032),    # 手机直出照片（iPhone）
        (7680, 4320),    # 8K
    ]
    sch = MultimodalScheduler()
    text_prompt_tokens = 200
    for w, h, tokens in resolution_sweep(sizes):
        prefill_ms = round(tokens * sch.cost.llm_ms_per_token, 1)
        ratio = round(tokens / text_prompt_tokens, 1)
        print(
            f"  {w}x{h:<6} -> {tokens:5d} visual tokens | "
            f"prefill {prefill_ms:7.1f} ms | = {ratio:6.1f}x text prompt({text_prompt_tokens})"
        )


def scenario_2_mixed_batching() -> None:
    print()
    print("=" * 70)
    print("场景 2：同 batch 图文混合 vs 纯文本（encoder 与 LLM 重叠）")
    print("=" * 70)
    sch = MultimodalScheduler()
    photo = (3024, 4032)
    r = sch.compare_mixed_vs_text(4, text_tokens=200, image_size=photo)
    mixed, text_only = r["mixed"], r["text_only"]
    print(f"  batch: 4 请求 x 200 text tokens" + (" + 1 照片/请求" if mixed.n_images else ""))
    print(f"  text-only : llm_prefill {text_only.llm_prefill_ms:8.2f} ms")
    print(
        f"  mixed     : llm_prefill {mixed.llm_prefill_ms:8.2f} ms "
        f"(visual {mixed.visual_tokens} tokens, share {r['visual_share']*100:.1f}%)"
    )
    print(f"  encoder   : {mixed.encoder_patches} patches, {mixed.encoder_ms} ms (overlap 不阻塞)")
    print(f"  makespan  : {mixed.makespan_ms} ms | serial {mixed.serial_ms} ms")
    print(f"  prefill slowdown: {r['prefill_slowdown']}x")


def scenario_3_latency_budget() -> None:
    print()
    print("=" * 70)
    print("场景 3：600ms 语音响应预算分解与瓶颈定位")
    print("=" * 70)
    breakdown = first_audio_breakdown(DEFAULT_CONFIG)
    for name, ms in breakdown["stages"].items():
        print(f"  {name:<16} {ms:7.1f} ms")
    print(f"  {'total':<16} {breakdown['total_ms']:7.1f} ms")
    head = budget_headroom(DEFAULT_CONFIG, budget_ms=600.0)
    print(f"  budget 600 ms -> headroom {head['headroom_ms']} ms (meets={head['meets_budget']})")
    print("  每段砍半的收益：")
    for row in optimization_table(DEFAULT_CONFIG, budget_ms=600.0):
        print(
            f"    {row['stage']:<16} {row['original_ms']:6.0f} -> {row['improved_ms']:5.1f} ms"
            f" | total {row['new_total_ms']:6.2f} ms | gain {row['gain_ms']:6.2f} ms"
        )


def scenario_4_codec() -> None:
    print()
    print("=" * 70)
    print("场景 4：1 分钟语音的 codec token 账（Mimi vs EnCodec）")
    print("=" * 70)
    specs = [MIMI, ENCODEC_6K, ENCODEC_1_5K]
    for row in compare_codecs(specs, seconds=60.0):
        print(
            f"  {row['name']:<14} frames {row['frames']:5d} | tokens {row['tokens']:5d}"
            f" | semantic {row['semantic_tokens']:4d} | {row['bit_rate_bps']:7.0f} bps"
        )
    growth = kv_growth_per_minute(specs, text_tokens_per_minute=200.0)
    for name, ratio in growth.items():
        print(f"  KV 压力 {name:<10} : 1 分钟语音 = {ratio} 倍文本 token 量(200/min)")


def scenario_5_duplex_trace() -> None:
    print()
    print("=" * 70)
    print("场景 5：双工对话 trace（真打断 + 一次误触发恢复）")
    print("=" * 70)
    s = DuplexSession()
    # 用户提问，Agent 回答，中途被打断
    s.step(0, Event.USER_SPEECH_START)
    s.step(1200, Event.USER_SPEECH_END)
    s.step(1450, Event.RESPONSE_READY, duration_ms=4000)
    s.advance_playback(2000, 400)   # 播放了 400ms
    s.step(2100, Event.USER_SPEECH_START)   # 用户抢话
    s.step(2200, Event.SPEECH_CONFIRMED)    # 确认是真打断
    s.step(3400, Event.USER_SPEECH_END)
    s.step(3650, Event.RESPONSE_READY, duration_ms=2500)
    s.advance_playback(4200, 500)
    s.step(4300, Event.USER_SPEECH_START)   # 咳嗽 -> 误触发
    s.step(4450, Event.SPEECH_FALSE_ALARM)  # 无实际内容，恢复播放
    s.advance_playback(7000, 2500)
    s.step(7000, Event.RESPONSE_DONE)
    for t in s.transitions:
        note = f" | {t.note}" if t.note else ""
        print(f"  {t.at_ms:6d} ms  {t.event.value:<20} {t.from_state.value:>11} -> {t.to_state.value:<11}{note}")
    print(
        f"  interruptions={s.interruptions} false_alarms={s.false_alarms} "
        f"turns_completed={s.turns_completed}"
    )
    print("  读法：第一次打断把 LLM 历史截断到用户实际听到的 400ms；")
    print("        误触发（咳嗽）不截断历史，恢复播放剩余内容。")


def scenario_6_interrupt_latency() -> None:
    print()
    print("=" * 70)
    print("场景 6：打断后的二次响应延迟 vs 正常轮次")
    print("=" * 70)
    normal = first_audio_breakdown(DEFAULT_CONFIG)["total_ms"]
    intr = interrupt_response_latency(DEFAULT_CONFIG)
    print(f"  正常轮次 first-audio : {normal:7.2f} ms")
    print(
        f"  打断重响应           : {intr['total_ms']:7.2f} ms "
        f"(vad {intr['vad_trigger_ms']} + cancel {intr['cancel_ms']} + restart {intr['pipeline_restart_ms']})"
    )
    print(f"  打断代价             : {round(intr['total_ms'] - normal, 2):7.2f} ms")


def run_demo() -> None:
    scenario_1_resolution_sweep()
    scenario_2_mixed_batching()
    scenario_3_latency_budget()
    scenario_4_codec()
    scenario_5_duplex_trace()
    scenario_6_interrupt_latency()


if __name__ == "__main__":
    run_demo()
