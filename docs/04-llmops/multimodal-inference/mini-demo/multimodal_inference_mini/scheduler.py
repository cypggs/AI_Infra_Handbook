"""Multimodal request scheduling: visual token counting and mixed batching.

Models the production pattern used by vLLM / SGLang / TensorRT-LLM serving
stacks for vision-language models:

1. A vision encoder runs on (a) separate worker(s); images are not tokens
   until the encoder + projector have turned them into embeddings.
2. The LLM prefill cost of a multimodal request is dominated by the number
   of *visual tokens* (patches) the image becomes inside the language model,
   not by the raw pixel count.
3. Text-only and multimodal requests are batched together; the encoder is
   a second, CPU/GPU-affine resource that must be scheduled too.

All numbers are deterministic; no randomness, no GPU required.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Visual token counting (Qwen2.5-VL style dynamic resolution)
# ---------------------------------------------------------------------------

# Qwen2.5-VL defaults: images are rescaled so that their pixel count falls in
# [min_pixels, max_pixels], then merged into (merge_size x merge_size) patches
# of 28x28 raw pixels (patch 14 x merge 2). The visual token count is
# therefore clamped to [min_tokens, max_tokens] = [256, 1280].
QWEN_MIN_PIXELS = 256 * 28 * 28
QWEN_MAX_PIXELS = 1280 * 28 * 28
QWEN_TOKENS_PER_PATCH = 28 * 28


def visual_token_count(
    width: int,
    height: int,
    min_pixels: int = QWEN_MIN_PIXELS,
    max_pixels: int = QWEN_MAX_PIXELS,
    pixels_per_token: int = QWEN_TOKENS_PER_PATCH,
) -> int:
    """Visual tokens for one image under dynamic-resolution patching.

    The image is scaled so width*height lands inside [min_pixels, max_pixels]
    (aspect ratio preserved), each side is rounded down to a whole number of
    28x28 merge blocks, and tokens = blocks_w * blocks_h.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width/height must be positive")
    if min_pixels <= 0 or max_pixels < min_pixels:
        raise ValueError("invalid pixel clamp range")

    pixels = width * height
    if pixels > max_pixels:
        scale = (max_pixels / pixels) ** 0.5
        w, h = width * scale, height * scale
    elif pixels < min_pixels:
        scale = (min_pixels / pixels) ** 0.5
        w, h = width * scale, height * scale
    else:
        w, h = float(width), float(height)

    block = pixels_per_token**0.5  # 28
    blocks_w = max(1, int(w // block))
    blocks_h = max(1, int(h // block))
    tokens = blocks_w * blocks_h

    max_tokens = max_pixels // pixels_per_token
    min_tokens = min_pixels // pixels_per_token
    return max(min_tokens, min(max_tokens, tokens))


def resolution_sweep(
    sizes: list[tuple[int, int]],
    **kwargs,
) -> list[tuple[int, int, int]]:
    """Return [(width, height, tokens)] for a list of image sizes."""
    return [(w, h, visual_token_count(w, h, **kwargs)) for w, h in sizes]


# ---------------------------------------------------------------------------
# Requests and scheduling
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Request:
    """One serving request. images = list of (width, height)."""

    req_id: str
    text_tokens: int
    images: tuple[tuple[int, int], ...] = ()
    arrival_ms: int = 0

    def visual_tokens(self, **kwargs) -> int:
        return sum(visual_token_count(w, h, **kwargs) for w, h in self.images)


@dataclass(frozen=True)
class StageCost:
    """Cost model constants (per unit, in milliseconds)."""

    llm_ms_per_token: float = 0.05        # batched prefill throughput token
    encoder_ms_per_patch: float = 0.02    # vision encoder latency per patch
    encoder_batch_patch_per_ms: float = 64.0  # encoder throughput (patches/ms)


@dataclass(frozen=True)
class ScheduleResult:
    n_requests: int
    n_images: int
    text_tokens: int
    visual_tokens: int
    encoder_patches: int
    llm_prefill_ms: float
    encoder_ms: float
    makespan_ms: float          # max(prefill, encoder) when overlapped
    serial_ms: float            # prefill + encoder without overlap
    text_only_baseline_ms: float  # same batch, images stripped


class MultimodalScheduler:
    """Simulates batched scheduling of text-only + multimodal requests.

    The LLM prefill engine and the vision encoder run on different workers,
    so by default they overlap: makespan = max(llm_prefill, encoder).
    """

    def __init__(self, cost: StageCost | None = None, overlap: bool = True):
        self.cost = cost or StageCost()
        self.overlap = overlap

    def llm_tokens(self, req: Request) -> int:
        """Tokens the LLM must prefill for this request."""
        return req.text_tokens + req.visual_tokens()

    def encoder_patches(self, req: Request) -> int:
        """Raw 14x14 patches fed to the vision encoder (merge_size=2)."""
        return sum(
            visual_token_count(w, h) * 4 for w, h in req.images
        )

    def schedule(self, requests: list[Request]) -> ScheduleResult:
        text_tokens = sum(r.text_tokens for r in requests)
        visual_tokens = sum(r.visual_tokens() for r in requests)
        patches = sum(self.encoder_patches(r) for r in requests)
        n_images = sum(len(r.images) for r in requests)

        # batched prefill: all tokens (text + visual) stream through the LLM
        llm_ms = float(
            (np.array([text_tokens + visual_tokens], dtype=np.float64)
             * self.cost.llm_ms_per_token).item()
        )
        # encoder throughput caps the batch benefit; latency floor = 1 patch cost
        encoder_ms = max(
            patches / self.cost.encoder_batch_patch_per_ms,
            self.cost.encoder_ms_per_patch,
        )

        text_only_ms = text_tokens * self.cost.llm_ms_per_token
        if self.overlap:
            makespan = max(llm_ms, encoder_ms) if n_images else llm_ms
        else:
            makespan = llm_ms + encoder_ms

        return ScheduleResult(
            n_requests=len(requests),
            n_images=n_images,
            text_tokens=text_tokens,
            visual_tokens=visual_tokens,
            encoder_patches=patches,
            llm_prefill_ms=round(llm_ms, 2),
            encoder_ms=round(encoder_ms, 2),
            makespan_ms=round(makespan, 2),
            serial_ms=round(llm_ms + encoder_ms, 2),
            text_only_baseline_ms=round(text_only_ms, 2),
        )

    def compare_mixed_vs_text(
        self, n_requests: int, text_tokens: int, image_size: tuple[int, int]
    ) -> dict:
        """Same batch with vs without one image per request."""
        mixed = [
            Request(
                f"m{i}", text_tokens, images=(image_size,), arrival_ms=i * 10
            )
            for i in range(n_requests)
        ]
        text_only = [Request(f"t{i}", text_tokens, arrival_ms=i * 10) for i in range(n_requests)]
        r_mixed = self.schedule(mixed)
        r_text = self.schedule(text_only)
        return {
            "mixed": r_mixed,
            "text_only": r_text,
            "prefill_slowdown": round(
                r_mixed.llm_prefill_ms / max(r_text.llm_prefill_ms, 1e-9), 3
            ),
            "visual_share": round(
                r_mixed.visual_tokens / max(r_mixed.text_tokens + r_mixed.visual_tokens, 1),
                4,
            ),
        }
