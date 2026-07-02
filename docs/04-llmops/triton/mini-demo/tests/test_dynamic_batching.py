"""Tests for dynamic batching and server inference."""
import tempfile
from pathlib import Path

import numpy as np
import pytest

from triton_mini import DynamicBatcher, InferenceRequest, TritonServer


CLASSIFY_CONFIG = """
name: "classify"
backend: "classification"
max_batch_size: 8
input [ { name: "x" data_type: TYPE_FP32 dims: [16] } ]
output [
  { name: "class" data_type: TYPE_INT64 dims: [1] }
]
dynamic_batching {
  preferred_batch_size: [2, 4]
  max_queue_delay_microseconds: 0
}
"""


def _build_repo() -> str:
    tmpdir = tempfile.mkdtemp()
    model_dir = Path(tmpdir) / "classify"
    model_dir.mkdir()
    (model_dir / "config.pbtxt").write_text(CLASSIFY_CONFIG, encoding="utf-8")
    return tmpdir


def test_dynamic_batcher_preferred_size():
    batcher = DynamicBatcher(max_batch_size=8, preferred_batch_size=[2, 4])
    requests = [
        InferenceRequest(str(i), "classify", {"x": np.zeros((1, 16), dtype=np.float32)})
        for i in range(5)
    ]
    batches = batcher.schedule(requests)
    assert len(batches) == 2
    assert len(batches[0]) == 4
    assert len(batches[1]) == 1


def test_dynamic_batcher_falls_back_to_max():
    batcher = DynamicBatcher(max_batch_size=3, preferred_batch_size=[2])
    requests = [
        InferenceRequest(str(i), "classify", {"x": np.zeros((1, 16), dtype=np.float32)})
        for i in range(7)
    ]
    batches = batcher.schedule(requests)
    assert sum(len(b) for b in batches) == 7
    for batch in batches:
        assert len(batch) <= 3


def test_server_infer_batch():
    repo = _build_repo()
    server = TritonServer(repo).load()
    inputs_list = [{"x": np.random.randn(1, 16).astype(np.float32)} for _ in range(5)]
    outputs = server.infer_batch("classify", inputs_list)
    assert len(outputs) == 5
    for out in outputs:
        assert "class" in out
        assert out["class"].shape[0] == 1


def test_server_infer_single():
    repo = _build_repo()
    server = TritonServer(repo).load()
    inputs = {"x": np.random.randn(1, 16).astype(np.float32)}
    outputs = server.infer("classify", inputs)
    assert "class" in outputs
    assert outputs["class"].shape == (1, 1)
