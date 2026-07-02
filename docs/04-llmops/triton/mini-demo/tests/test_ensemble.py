"""Tests for ensemble scheduling."""
import tempfile
from pathlib import Path

import numpy as np
import pytest

from triton_mini import TritonServer


REPO_CONFIGS = {
    "tokenize": """
name: "tokenize"
backend: "python"
max_batch_size: 0
input [ { name: "raw" data_type: TYPE_INT64 dims: [1] } ]
output [ { name: "INPUT_IDS" data_type: TYPE_INT64 dims: [-1] } ]
""",
    "generate": """
name: "generate"
backend: "vllm"
max_batch_size: 0
input [ { name: "INPUT_IDS" data_type: TYPE_INT64 dims: [-1] } ]
output [ { name: "OUTPUT_IDS" data_type: TYPE_INT64 dims: [1] } ]
""",
    "postprocess": """
name: "postprocess"
backend: "python"
max_batch_size: 0
input [ { name: "OUTPUT_IDS" data_type: TYPE_INT64 dims: [1] } ]
output [ { name: "final" data_type: TYPE_INT64 dims: [1] } ]
""",
    "pipeline": """
name: "pipeline"
platform: "ensemble"
max_batch_size: 0
input [ { name: "raw" data_type: TYPE_INT64 dims: [1] } ]
output [ { name: "final" data_type: TYPE_INT64 dims: [1] } ]
ensemble_scheduling {
  step [
    {
      model_name: "tokenize"
      model_version: -1
      input_map { key: "raw" value: "raw" }
      output_map { key: "INPUT_IDS" value: "input_ids" }
    },
    {
      model_name: "generate"
      model_version: -1
      input_map { key: "INPUT_IDS" value: "input_ids" }
      output_map { key: "OUTPUT_IDS" value: "output_ids" }
    },
    {
      model_name: "postprocess"
      model_version: -1
      input_map { key: "OUTPUT_IDS" value: "output_ids" }
      output_map { key: "final" value: "final" }
    }
  ]
}
""",
}


def _build_repo() -> str:
    tmpdir = tempfile.mkdtemp()
    repo = Path(tmpdir)
    for name, text in REPO_CONFIGS.items():
        model_dir = repo / name
        model_dir.mkdir()
        (model_dir / "config.pbtxt").write_text(text, encoding="utf-8")
    return tmpdir


def test_ensemble_pipeline():
    repo = _build_repo()
    server = TritonServer(repo).load()
    inputs = {"raw": np.array([[1]], dtype=np.int64)}
    outputs = server.infer("pipeline", inputs)
    assert "final" in outputs
    assert outputs["final"].shape == (1, 1)


def test_ensemble_missing_tensor_raises():
    """An ensemble step with an unresolved tensor should raise a clear error."""
    bad_config = """
name: "bad_pipeline"
platform: "ensemble"
max_batch_size: 0
input [ { name: "raw" data_type: TYPE_INT64 dims: [1] } ]
output [ { name: "final" data_type: TYPE_INT64 dims: [1] } ]
ensemble_scheduling {
  step [
    {
      model_name: "generate"
      model_version: -1
      input_map { key: "INPUT_IDS" value: "missing_tensor" }
      output_map { key: "OUTPUT_IDS" value: "final" }
    }
  ]
}
"""
    tmpdir = tempfile.mkdtemp()
    repo = Path(tmpdir)
    model_dir = repo / "bad_pipeline"
    model_dir.mkdir()
    (model_dir / "config.pbtxt").write_text(bad_config, encoding="utf-8")
    # Also add generate model so the repo loads successfully.
    generate_dir = repo / "generate"
    generate_dir.mkdir()
    (generate_dir / "config.pbtxt").write_text(REPO_CONFIGS["generate"], encoding="utf-8")

    server = TritonServer(tmpdir).load()
    with pytest.raises(Exception):
        server.infer("bad_pipeline", {"raw": np.array([[1]], dtype=np.int64)})
