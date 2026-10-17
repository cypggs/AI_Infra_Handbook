"""首 token 延迟（TTFT）与流式渲染对用户感知延迟的影响模型。

对应主题章节：docs/09-case-study/perplexity/02-core-ideas（速度即产品）。
核心观点：流式把"等待整段答案"变成"等待第一个词元"，感知延迟由 TTFT 主导。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamConfig:
    ttft_s: float        # 首 token 延迟
    tokens_per_s: float  # 解码吞吐
    chunk_size: int = 8  # 每个网络块的 token 数（影响渲染粒度）


def total_time(config: StreamConfig, n_tokens: int) -> float:
    """整段答案生成完毕的墙钟时间。"""
    return config.ttft_s + n_tokens / config.tokens_per_s


def perceived_latency_nonstreaming(config: StreamConfig, n_tokens: int) -> float:
    """非流式：用户看到任何东西之前要等全部生成完。"""
    return total_time(config, n_tokens)


def perceived_latency_streaming(config: StreamConfig, n_tokens: int,
                                read_tokens: int | None = None) -> float:
    """流式：感知延迟 = TTFT + 读完前 read_tokens 个 token 的时间。

    read_tokens 为 None 时取全部（即完整阅读时间，与不流式的墙钟一致，
    但用户始终"有内容可看"）。
    """
    k = n_tokens if read_tokens is None else min(read_tokens, n_tokens)
    return config.ttft_s + k / config.tokens_per_s


def first_render_time(config: StreamConfig) -> float:
    """第一个可见渲染块出现的时间（TTFT + 第一块解码时间）。"""
    return config.ttft_s + min(config.chunk_size, 1) / config.tokens_per_s


def perceived_speedup(config: StreamConfig, n_tokens: int,
                      read_tokens: int) -> float:
    """流式相对非流式的感知延迟加速比。"""
    return (perceived_latency_nonstreaming(config, n_tokens)
            / perceived_latency_streaming(config, n_tokens, read_tokens))


def sensitivity(config: StreamConfig, n_tokens: int,
                read_tokens: int) -> dict:
    """量化 TTFT 与吞吐对感知延迟的弹性：各扰动 10% 后的变化率。"""
    base = perceived_latency_streaming(config, n_tokens, read_tokens)
    ttft_up = StreamConfig(config.ttft_s * 1.1,
                           config.tokens_per_s, config.chunk_size)
    tput_down = StreamConfig(config.ttft_s, config.tokens_per_s / 1.1,
                             config.chunk_size)
    return {
        "base_s": base,
        "ttft_plus10pct_s": perceived_latency_streaming(ttft_up, n_tokens, read_tokens),
        "tput_minus10pct_s": perceived_latency_streaming(tput_down, n_tokens, read_tokens),
        "ttft_share": config.ttft_s / base,
    }
