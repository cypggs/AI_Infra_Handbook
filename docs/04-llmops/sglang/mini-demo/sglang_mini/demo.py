"""Entry point for the Mini SGLang demo.

This script shows two core SGLang ideas in pure Python:
1. RadixAttention-style automatic prefix caching across multiple requests.
2. Regex-constrained structured generation.
"""

from sglang_mini.cache_manager import RadixCacheManager
from sglang_mini.runtime import MiniRuntime


def char_tokens(text: str) -> list:
    """Encode a string as ASCII token ids."""
    return [ord(c) for c in text]


def decode_tokens(tokens: list) -> str:
    return "".join(chr(t) for t in tokens if 32 <= t <= 126)


def demo_radix_attention():
    print("\n=== Demo 1: RadixAttention prefix sharing ===\n")

    vocab = list(range(32, 127))  # printable ASCII
    cache = RadixCacheManager(max_nodes=256)
    runtime = MiniRuntime(vocab=vocab, cache_manager=cache)

    system_prompt = char_tokens("You are a helpful assistant. ")
    user_a = char_tokens("What is the capital of France?")
    user_b = char_tokens("What is the capital of Germany?")

    # Request 1: long system prompt + first user query.
    req1 = runtime.add_request("req-1", system_prompt + user_a)
    out1 = runtime.generate(req1)
    print(f"[req-1] prefix_len={runtime.cache._request_contexts['req-1'].prefix_len}")
    print(f"[req-1] generated: {out1[:60]}...")

    # Request 2: same system prompt, different user query.
    req2 = runtime.add_request("req-2", system_prompt + user_b)
    ctx2 = runtime.cache._request_contexts["req-2"]
    print(f"[req-2] prefix_len={ctx2.prefix_len} (system prompt shared!)")
    out2 = runtime.generate(req2)
    print(f"[req-2] generated: {out2[:60]}...")

    stats = runtime.cache_stats()
    print(f"\nCache stats: {stats}")
    print(f"Prefix hit rate: {cache.hit_rate():.1%}")

    runtime.release(req1)
    runtime.release(req2)


def demo_structured_generation():
    print("\n=== Demo 2: Structured generation (regex constraint) ===\n")

    vocab = list(range(32, 127))
    runtime = MiniRuntime(vocab=vocab, seed=7)

    # Force the model to output a date in YYYY-MM-DD format.
    pattern = r"\d{4}-\d{2}-\d{2}"
    req = runtime.add_request(
        request_id="date-req",
        prompt_tokens=char_tokens("Today is "),
        pattern=pattern,
        max_new_tokens=12,
    )
    output = runtime.generate(req)
    print(f"Pattern: {pattern}")
    print(f"Generated: {output}")
    print(f"Matches regex? {len(output) == 10 and output[4] == '-' and output[7] == '-'}")

    runtime.release(req)


def demo_json_like():
    print("\n=== Demo 3: Structured generation (simple alternation) ===\n")

    vocab = list(range(32, 127))
    runtime = MiniRuntime(vocab=vocab, seed=11)

    # Force the model to pick one of the allowed colors.
    pattern = r"(red|blue|green)"
    req = runtime.add_request(
        request_id="color-req",
        prompt_tokens=char_tokens("Favorite color: "),
        pattern=pattern,
        max_new_tokens=8,
    )
    output = runtime.generate(req)
    print(f"Pattern: {pattern}")
    print(f"Generated: {output}")

    runtime.release(req)


if __name__ == "__main__":
    demo_radix_attention()
    demo_structured_generation()
    demo_json_like()
    print("\nMini SGLang demo finished.")
