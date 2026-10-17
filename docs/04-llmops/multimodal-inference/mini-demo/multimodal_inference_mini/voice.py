"""Voice interaction latency budget model.

A voice agent's perceived responsiveness is dominated by the time from
"user stopped talking" to "first audio byte played back". That time is the
sum of a fixed pipeline of stages, each with a tunable budget:

    user silence ──▶ VAD endpointing ──▶ STT finalize ──▶ LLM TTFT
                 ──▶ TTS first frame ──▶ transport ──▶ playback

Interruption (barge-in) re-prices the same pipeline: VAD must *fire* while
the agent is speaking, the in-flight response must be cancelled, and the new
pipeline must start -- all within a budget users experience as "the agent
heard me immediately".

All values are analytic (no simulation noise); units are milliseconds.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class VoiceConfig:
    """Per-stage latency assumptions (p50-style steady-state values)."""

    endpointing_ms: float = 240.0    # VAD silence window before turn closes
    stt_finalize_ms: float = 150.0   # partial transcript -> committed text
    llm_ttft_ms: float = 300.0       # first token of the response
    tts_first_frame_ms: float = 120.0  # first playable audio chunk
    transport_ms: float = 40.0       # one-way network + playback buffer
    interrupt_vad_ms: float = 80.0   # VAD fire latency mid-speech
    cancel_ms: float = 30.0          # stop TTS/LLM, truncate history


DEFAULT_CONFIG = VoiceConfig()


def first_audio_breakdown(config: VoiceConfig = DEFAULT_CONFIG) -> dict:
    """Stage-by-stage time from end-of-speech to first audio byte."""
    stages = [
        ("endpointing", config.endpointing_ms),
        ("stt_finalize", config.stt_finalize_ms),
        ("llm_ttft", config.llm_ttft_ms),
        ("tts_first_frame", config.tts_first_frame_ms),
        ("transport", config.transport_ms),
    ]
    total = sum(ms for _, ms in stages)
    return {
        "stages": dict(stages),
        "total_ms": round(total, 2),
    }


def budget_headroom(config: VoiceConfig = DEFAULT_CONFIG, budget_ms: float = 600.0):
    """How much slack each stage has against a response-latency SLO.

    A stage is "over budget" when the residual after all other stages is
    negative, i.e. the SLO is unreachable no matter how this stage is tuned.
    """
    breakdown = first_audio_breakdown(config)
    residual = budget_ms - breakdown["total_ms"]
    per_stage = {}
    others_total = breakdown["total_ms"]
    for name, ms in breakdown["stages"].items():
        others = others_total - ms
        per_stage[name] = round(budget_ms - others, 2)
    return {
        "budget_ms": budget_ms,
        "total_ms": breakdown["total_ms"],
        "headroom_ms": round(residual, 2),
        "meets_budget": residual >= 0,
        "max_allowable_ms": per_stage,
    }


def interrupt_response_latency(config: VoiceConfig = DEFAULT_CONFIG) -> dict:
    """Time from user speaking over the agent to the new response's audio.

    The pipeline restarts after the in-flight generation is cancelled.
    """
    cancel_overhead = config.interrupt_vad_ms + config.cancel_ms
    restart = first_audio_breakdown(config)["total_ms"]
    return {
        "vad_trigger_ms": config.interrupt_vad_ms,
        "cancel_ms": config.cancel_ms,
        "pipeline_restart_ms": round(restart, 2),
        "total_ms": round(cancel_overhead + restart, 2),
    }


def tune(config: VoiceConfig, **overrides) -> VoiceConfig:
    """Return a copy of `config` with selected stages overridden."""
    return replace(config, **overrides)


def optimization_table(
    config: VoiceConfig = DEFAULT_CONFIG, budget_ms: float = 600.0
) -> list[dict]:
    """Show the effect of halving each stage, one at a time."""
    base = first_audio_breakdown(config)["total_ms"]
    rows = []
    for stage, ms in first_audio_breakdown(config)["stages"].items():
        improved = tune(config, **{f"{stage}_ms": ms / 2.0})
        new_total = first_audio_breakdown(improved)["total_ms"]
        rows.append(
            {
                "stage": stage,
                "original_ms": ms,
                "improved_ms": ms / 2.0,
                "new_total_ms": round(new_total, 2),
                "gain_ms": round(base - new_total, 2),
                "headroom_after_ms": round(budget_ms - new_total, 2),
            }
        )
    return rows
