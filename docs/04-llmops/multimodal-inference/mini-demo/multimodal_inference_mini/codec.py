"""Audio codec token simulation: frame rate, bitrate and token accounting.

Real speech-to-speech models do not emit text tokens: they emit *codec
tokens* -- vector-quantized codes from a neural audio codec. The codec
defines three numbers that drive everything downstream:

- frame_rate_hz: how many frames (one code per codebook per frame) per second
- codebooks:     how many residual vector-quantizer stages per frame
- codebook_size: vocabulary of each stage (bits per token = log2(size))

From these we get tokens/second, bitrate, and -- critically for the serving
stack -- how fast a spoken context fills up the KV cache.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CodecSpec:
    """A neural audio codec configuration."""

    name: str
    sample_rate_hz: int
    frame_rate_hz: float       # codec frames per second
    codebooks: int             # RVQ stages per frame
    codebook_size: int         # vocabulary per stage
    semantic_codebooks: int = 0  # leading stages carrying semantic content

    @property
    def bits_per_token(self) -> int:
        return max(1, math.ceil(math.log2(self.codebook_size)))

    @property
    def tokens_per_frame(self) -> int:
        return self.codebooks

    @property
    def tokens_per_second(self) -> float:
        return self.frame_rate_hz * self.codebooks

    @property
    def bit_rate(self) -> float:
        """Audio payload bitrate in bits per second."""
        return self.tokens_per_second * self.bits_per_token

    @property
    def frame_latency_ms(self) -> float:
        """Time spanned by one codec frame."""
        return 1000.0 / self.frame_rate_hz

    def tokens_for_duration(self, seconds: float) -> int:
        """Total codec tokens for `seconds` of audio."""
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        return math.ceil(seconds * self.tokens_per_second)

    def semantic_tokens_for_duration(self, seconds: float) -> int:
        """Tokens in the semantic (understanding-critical) subset."""
        if self.semantic_codebooks == 0:
            return 0
        return math.ceil(seconds * self.frame_rate_hz * self.semantic_codebooks)

    def seconds_for_tokens(self, tokens: int) -> float:
        if tokens < 0:
            raise ValueError("tokens must be non-negative")
        return tokens / self.tokens_per_second


# Published configurations (approximate, from the respective papers/repos):
# - Mimi (Kyutai, used by Moshi): 12.5 Hz frames, 8 codebooks (~1.1 kbps @24kHz),
#   first 2 codebooks are the semantic stream.
# - EnCodec 24kHz @6kbps (Meta): 75 Hz frames, 8 codebooks of 1024 entries.
# - EnCodec 24kHz @1.5kbps: 75 Hz frames, 2 codebooks (aggressive compression).
MIMI = CodecSpec(
    name="mimi",
    sample_rate_hz=24_000,
    frame_rate_hz=12.5,
    codebooks=8,
    codebook_size=2048,
    semantic_codebooks=2,
)
ENCODEC_6K = CodecSpec(
    name="encodec_6k",
    sample_rate_hz=24_000,
    frame_rate_hz=75.0,
    codebooks=8,
    codebook_size=1024,
)
ENCODEC_1_5K = CodecSpec(
    name="encodec_1_5k",
    sample_rate_hz=24_000,
    frame_rate_hz=75.0,
    codebooks=2,
    codebook_size=1024,
)


def compare_codecs(specs: list[CodecSpec], seconds: float) -> list[dict]:
    """Side-by-side accounting for a fixed audio duration."""
    rows = []
    for spec in specs:
        rows.append(
            {
                "name": spec.name,
                "frames": math.ceil(seconds * spec.frame_rate_hz),
                "tokens": spec.tokens_for_duration(seconds),
                "semantic_tokens": spec.semantic_tokens_for_duration(seconds),
                "bit_rate_bps": spec.bit_rate,
                "frame_latency_ms": spec.frame_latency_ms,
            }
        )
    return rows


def kv_growth_per_minute(
    specs: list[CodecSpec], text_tokens_per_minute: float = 200.0
) -> dict[str, float]:
    """Codec tokens generated per minute of conversation vs. text tokens.

    Returns {spec_name: ratio} of audio tokens to text tokens for the same
    minute of dialogue -- the number that decides whether audio contexts fit
    in the KV budget.
    """
    out = {}
    for spec in specs:
        audio = spec.tokens_for_duration(60.0)
        out[spec.name] = round(audio / max(text_tokens_per_minute, 1e-9), 2)
    return out


def streaming_chunk_plan(
    spec: CodecSpec, seconds: float, chunk_ms: float = 80.0
) -> list[tuple[float, float, int]]:
    """Split `seconds` of audio into streaming chunks of `chunk_ms`.

    Returns [(chunk_start_s, chunk_end_s, n_tokens)]; the final chunk may be
    short. The last chunk's token count reflects the partial frame remainder.
    """
    if chunk_ms <= 0:
        raise ValueError("chunk_ms must be positive")
    chunks = []
    start = 0.0
    while start < seconds:
        end = min(seconds, start + chunk_ms / 1000.0)
        n_tokens = math.ceil(round((end - start) * spec.tokens_per_second, 6))
        chunks.append((round(start, 4), round(end, 4), n_tokens))
        start = end
    return chunks
