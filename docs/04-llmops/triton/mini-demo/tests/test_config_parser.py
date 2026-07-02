"""Tests for config.pbtxt parsing."""
import pytest

from triton_mini import ConfigParser


SAMPLE_CONFIG = """
name: "my_model"
platform: "onnxruntime_onnx"
max_batch_size: 8
input [
  {
    name: "input"
    data_type: TYPE_FP32
    dims: [-1, 3, 224, 224]
  }
]
output [
  {
    name: "output"
    data_type: TYPE_FP32
    dims: [1000]
  }
]
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [0, 1]
  }
]
dynamic_batching {
  preferred_batch_size: [2, 4]
  max_queue_delay_microseconds: 5000
  preserve_ordering: true
}
parameters: {
  key: "threshold"
  value: { string_value: "0.5" }
}
parameters: {
  key: "enable_fp16"
  value: { string_value: "true" }
}
"""


def test_parse_basic_fields():
    config = ConfigParser().parse_text(SAMPLE_CONFIG)
    assert config.name == "my_model"
    assert config.platform == "onnxruntime_onnx"
    assert config.max_batch_size == 8


def test_parse_inputs_outputs():
    config = ConfigParser().parse_text(SAMPLE_CONFIG)
    assert len(config.inputs) == 1
    assert config.inputs[0].name == "input"
    assert config.inputs[0].data_type == "TYPE_FP32"
    assert config.inputs[0].dims == [-1, 3, 224, 224]
    assert len(config.outputs) == 1
    assert config.outputs[0].name == "output"
    assert config.outputs[0].dims == [1000]


def test_parse_instance_group():
    config = ConfigParser().parse_text(SAMPLE_CONFIG)
    assert len(config.instance_groups) == 1
    ig = config.instance_groups[0]
    assert ig.count == 2
    assert ig.kind == "KIND_GPU"
    assert ig.gpus == [0, 1]


def test_parse_dynamic_batching():
    config = ConfigParser().parse_text(SAMPLE_CONFIG)
    assert config.dynamic_batching is not None
    assert config.dynamic_batching.preferred_batch_size == [2, 4]
    assert config.dynamic_batching.max_queue_delay_microseconds == 5000
    assert config.dynamic_batching.preserve_ordering is True


def test_parse_parameters():
    config = ConfigParser().parse_text(SAMPLE_CONFIG)
    assert config.parameters["threshold"] == "0.5"
    assert config.parameters["enable_fp16"] == "true"


def test_parse_ensemble():
    text = """
name: "pipeline"
platform: "ensemble"
input [ { name: "raw" data_type: TYPE_INT64 dims: [1] } ]
output [ { name: "final" data_type: TYPE_INT64 dims: [1] } ]
ensemble_scheduling {
  step [
    {
      model_name: "preprocess"
      model_version: -1
      input_map { key: "raw" value: "raw" }
      output_map { key: "processed" value: "processed" }
    }
  ]
}
"""
    config = ConfigParser().parse_text(text)
    assert config.ensemble_scheduling is not None
    assert len(config.ensemble_scheduling.step) == 1
    step = config.ensemble_scheduling.step[0]
    assert step.model_name == "preprocess"
    assert step.model_version == -1
    assert step.input_map == {"raw": "raw"}
    assert step.output_map == {"processed": "processed"}
