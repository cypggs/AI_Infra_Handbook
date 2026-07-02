"""Tests for the Executor and IFB scheduler."""
from tensorrt_llm_mini import (
    Builder,
    BuildConfig,
    Executor,
    GPT,
    QuantConfig,
    Request,
    Runtime,
    SamplingParams,
    SchedulerConfig,
)


def make_engine():
    model = GPT(vocab_size=64, hidden_size=32, num_layers=2, num_heads=4, max_seq_len=64)
    build_config = BuildConfig(
        max_batch_size=8,
        max_input_len=32,
        max_seq_len=64,
        max_num_tokens=256,
        plugins=["GELUPlugin", "LookupPlugin"],
    )
    quant_config = QuantConfig(dtype="fp16")
    return Builder(build_config=build_config, quant_config=quant_config).build(model)


def test_runtime_generate():
    engine = make_engine()
    runtime = Runtime(engine)
    tokens = runtime.generate([1, 2, 3, 4, 5], SamplingParams(max_tokens=5))
    assert len(tokens) == 5


def test_executor_ifb_mixed_phases():
    engine = make_engine()
    # Limit token budget so not all prefills fit in one step.
    executor = Executor(engine, SchedulerConfig(max_batch_size=4, max_num_tokens=10))
    requests = [
        Request("r0", [1, 2, 3, 4, 5, 6, 7, 8], max_tokens=4),  # 8 prompt tokens
        Request("r1", [11, 12], max_tokens=4),                  # 2 prompt tokens
        Request("r2", [21, 22, 23], max_tokens=4),              # 3 prompt tokens
    ]
    responses = executor.generate_batch(requests)
    assert len(responses) == 3
    for resp in responses:
        assert len(resp.tokens) > 0

    # Verify that at least one step mixed context and generation requests
    # using fresh request objects so that prefill state is clean.
    mixed = False
    executor.reset()
    fresh_requests = [
        Request("r0", [1, 2, 3, 4, 5, 6, 7, 8], max_tokens=4),
        Request("r1", [11, 12], max_tokens=4),
        Request("r2", [21, 22, 23], max_tokens=4),
    ]
    executor.submit(fresh_requests)
    for _ in range(20):
        if not executor.waiting and not executor.running:
            break
        meta = executor.step()
        if meta["context"] and meta["generation"]:
            mixed = True
    assert mixed, "expected at least one step with both context and generation requests"


def test_executor_generation_priority():
    """Generation-phase requests should be scheduled before new context requests."""
    engine = make_engine()
    executor = Executor(engine, SchedulerConfig(max_batch_size=2, max_num_tokens=64))
    # One long-prompt request and one short-prompt request.
    long_req = Request("long", list(range(1, 21)), max_tokens=3)  # 20 prompt tokens
    short_req = Request("short", [31, 32], max_tokens=3)

    executor.submit([long_req])
    # Step 1: only long context can fit.
    meta1 = executor.step()
    assert meta1["context"] == ["long"]

    # Now add a short request. The running long decode should be scheduled first.
    executor.submit([short_req])
    meta2 = executor.step()
    assert "long" in meta2["generation"]
