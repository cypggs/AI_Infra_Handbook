"""Entry point demonstrating Builder, Runtime and Executor/IFB."""
from __future__ import annotations

from tensorrt_llm_mini import (
    BuildConfig,
    Builder,
    Executor,
    GPT,
    QuantConfig,
    Request,
    Runtime,
    SamplingParams,
    SchedulerConfig,
)


def build_tiny_engine(quant_dtype: str = "fp16"):
    """Build a tiny GPT engine with plugin fusion."""
    print("Building tiny GPT engine ...")
    model = GPT(vocab_size=64, hidden_size=32, num_layers=2, num_heads=4, max_seq_len=64)
    build_config = BuildConfig(
        max_batch_size=8,
        max_input_len=32,
        max_seq_len=64,
        max_num_tokens=256,
        precision=quant_dtype,
        plugins=["GELUPlugin", "LookupPlugin"],
    )
    quant_config = QuantConfig(dtype=quant_dtype)
    builder = Builder(build_config=build_config, quant_config=quant_config)
    engine = builder.build(model)
    summary = engine.summary()
    print(f"Engine summary: {summary}")
    return engine


def demo_single_request(engine):
    """Run a single request through the Runtime."""
    print("\n=== Demo 1: Runtime single-request generation ===")
    runtime = Runtime(engine)
    prompt = [1, 2, 3, 4, 5]
    tokens = runtime.generate(prompt, SamplingParams(max_tokens=12, temperature=0.5))
    print(f"Prompt ids:   {prompt}")
    print(f"Generated ids: {tokens}")


def demo_executor_ifb(engine):
    """Run multiple requests through the Executor to show IFB scheduling."""
    print("\n=== Demo 2: Executor with In-flight Batching ===")
    executor = Executor(
        engine,
        scheduler_config=SchedulerConfig(max_batch_size=8, max_num_tokens=64),
    )
    requests = [
        Request("req-A", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], max_tokens=6),
        Request("req-B", [11, 12, 13], max_tokens=8),
        Request("req-C", [21, 22, 23, 24, 25, 26, 27], max_tokens=5),
    ]
    executor.submit(requests)

    max_steps = 20
    for _ in range(max_steps):
        if not executor.waiting and not executor.running:
            break
        meta = executor.step()
        ctx = ",".join(meta["context"]) or "-"
        gen = ",".join(meta["generation"]) or "-"
        print(
            f"[Step {meta['step']:02d}] context=[{ctx}], generation=[{gen}], "
            f"scheduled={meta['scheduled']}"
        )

    print("\nFinished responses:")
    for resp in executor.finished:
        print(f"  {resp.req_id}: {resp.tokens}")


def main():
    engine = build_tiny_engine(quant_dtype="fp16")
    demo_single_request(engine)
    demo_executor_ifb(engine)


if __name__ == "__main__":
    main()
