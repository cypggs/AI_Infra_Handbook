"""Entry point that demonstrates the Mini Triton server end-to-end."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from triton_mini import TritonServer


CLASSIFY_CONFIG = """
name: "classify"
backend: "classification"
max_batch_size: 8
input [
  {
    name: "image"
    data_type: TYPE_FP32
    dims: [3, 224, 224]
  }
]
output [
  {
    name: "class"
    data_type: TYPE_INT64
    dims: [1]
  }
]
dynamic_batching {
  preferred_batch_size: [4]
  max_queue_delay_microseconds: 1000
}
"""

GENERATE_CONFIG = """
name: "generate"
backend: "vllm"
max_batch_size: 8
input [
  {
    name: "INPUT_IDS"
    data_type: TYPE_INT64
    dims: [-1]
  }
]
output [
  {
    name: "OUTPUT_IDS"
    data_type: TYPE_INT64
    dims: [1]
  }
]
dynamic_batching {
  preferred_batch_size: [4]
  max_queue_delay_microseconds: 1000
}
"""

TOKENIZE_CONFIG = """
name: "tokenize"
backend: "python"
max_batch_size: 0
input [
  {
    name: "raw"
    data_type: TYPE_INT64
    dims: [1]
  }
]
output [
  {
    name: "INPUT_IDS"
    data_type: TYPE_INT64
    dims: [-1]
  }
]
"""

POSTPROCESS_CONFIG = """
name: "postprocess"
backend: "python"
max_batch_size: 0
input [
  {
    name: "OUTPUT_IDS"
    data_type: TYPE_INT64
    dims: [1]
  }
]
output [
  {
    name: "final"
    data_type: TYPE_INT64
    dims: [1]
  }
]
"""

PIPELINE_CONFIG = """
name: "pipeline"
platform: "ensemble"
max_batch_size: 0
input [
  {
    name: "raw"
    data_type: TYPE_INT64
    dims: [1]
  }
]
output [
  {
    name: "final"
    data_type: TYPE_INT64
    dims: [1]
  }
]
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
"""


def _write_model(repo: Path, name: str, config_text: str) -> None:
    model_dir = repo / name
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.pbtxt").write_text(config_text, encoding="utf-8")


def _build_repo() -> str:
    tmpdir = tempfile.mkdtemp(prefix="triton_mini_repo_")
    repo = Path(tmpdir)
    _write_model(repo, "classify", CLASSIFY_CONFIG)
    _write_model(repo, "generate", GENERATE_CONFIG)
    _write_model(repo, "tokenize", TOKENIZE_CONFIG)
    _write_model(repo, "postprocess", POSTPROCESS_CONFIG)
    _write_model(repo, "pipeline", PIPELINE_CONFIG)
    return tmpdir


def _demo_classify(server: TritonServer) -> None:
    print("\n=== Demo 1: Dynamic Batching on classify ===")
    inputs_list = [
        {"image": np.random.randn(1, 3, 224, 224).astype(np.float32)}
        for _ in range(5)
    ]
    results = server.infer_batch("classify", inputs_list)
    print(f"Sent {len(results)} individual requests")
    for i, out in enumerate(results):
        print(f"  Request {i}: class={out['class'].item()}")


def _demo_generate(server: TritonServer) -> None:
    print("\n=== Demo 2: Dynamic Batching on generate (vLLM backend) ===")
    prompts = [
        np.array([[1, 2, 3, 4, 5]], dtype=np.int64),
        np.array([[10, 20]], dtype=np.int64),
        np.array([[7, 8, 9]], dtype=np.int64),
        np.array([[42]], dtype=np.int64),
        np.array([[3, 1, 4, 1, 5]], dtype=np.int64),
        np.array([[99, 100, 101, 102]], dtype=np.int64),
    ]
    results = server.infer_batch("generate", [{"INPUT_IDS": p} for p in prompts])
    print(f"Sent {len(results)} prompts")
    for i, out in enumerate(results):
        print(f"  Prompt {i}: next_token={out['OUTPUT_IDS'].item()}")


def _demo_ensemble(server: TritonServer) -> None:
    print("\n=== Demo 3: Ensemble pipeline (tokenize -> generate -> postprocess) ===")
    inputs = {"raw": np.array([[1]], dtype=np.int64)}
    outputs = server.infer("pipeline", inputs)
    print(f"  Ensemble output: final={outputs['final'].item()}")


def main() -> None:
    repo_path = _build_repo()
    print(f"Built temporary model repository at: {repo_path}")
    server = TritonServer(repo_path).load()
    print(f"Loaded models: {server.status()['models']}")

    _demo_classify(server)
    _demo_generate(server)
    _demo_ensemble(server)

    print("\n=== Metrics ===")
    print(server.metrics.report())


if __name__ == "__main__":
    main()
