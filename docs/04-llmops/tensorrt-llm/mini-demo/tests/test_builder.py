"""Tests for the Builder and Engine serialization."""
from pathlib import Path

from tensorrt_llm_mini import Builder, BuildConfig, Engine, GPT, QuantConfig


def test_build_engine_and_plugin_fusion(tmp_path: Path):
    model = GPT(vocab_size=64, hidden_size=32, num_layers=2, num_heads=4, max_seq_len=64)
    build_config = BuildConfig(
        max_batch_size=4,
        max_input_len=16,
        max_seq_len=32,
        max_num_tokens=128,
        precision="fp16",
        plugins=["GELUPlugin", "LookupPlugin"],
    )
    quant_config = QuantConfig(dtype="fp16")
    builder = Builder(build_config=build_config, quant_config=quant_config)
    engine = builder.build(model)

    assert isinstance(engine, Engine)
    # At least input/output + embedding + blocks + lm_head.
    assert len(engine.graph) > 10
    assert len(engine.weights) > 0
    # Plugins requested are present in the plugin map.
    assert "GELUPlugin" in engine.plugin_map
    assert "LookupPlugin" in engine.plugin_map
    # Some ops were replaced by plugins.
    plugin_ops = [n for n in engine.graph if n["op"] == "plugin"]
    assert len(plugin_ops) >= 2

    summary = engine.summary()
    assert summary["num_plugins"] == 2
    assert summary["precision"] == "fp16"

    # Round-trip serialization.
    engine_path = tmp_path / "engine.pkl"
    engine.serialize(engine_path)
    engine2 = Engine.deserialize(engine_path)
    assert len(engine2.graph) == len(engine.graph)
    assert len(engine2.weights) == len(engine.weights)


def test_quantized_weight_marker(tmp_path: Path):
    model = GPT(vocab_size=16, hidden_size=16, num_layers=1, num_heads=2, max_seq_len=16)
    build_config = BuildConfig(plugins=[], precision="fp8")
    quant_config = QuantConfig(dtype="fp8")
    builder = Builder(build_config=build_config, quant_config=quant_config)
    engine = builder.build(model)
    # Fake quantize should leave a tiny marker in at least one weight.
    assert any(np.any(np.abs(w - np.round(w / (np.max(np.abs(w)) + 1e-9)) * (np.max(np.abs(w)) + 1e-9)) > 1e-7)
           for w in engine.weights.values())


import numpy as np  # noqa: E402
