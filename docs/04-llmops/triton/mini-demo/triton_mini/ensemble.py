"""Ensemble scheduling for the Mini Triton demo."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

import numpy as np

from .config_parser import EnsembleScheduling, TritonConfig
from .scheduler import InferenceRequest, Scheduler

if TYPE_CHECKING:
    from .model_repository import ModelRepository


class EnsembleScheduler(Scheduler):
    """Scheduler for Triton ensemble models.

    An ensemble model itself does not execute kernels; it orchestrates a
    directed acyclic graph of sub-models by mapping inputs/outputs between
    steps.
    """

    def __init__(self, config: TritonConfig) -> None:
        self.config = config
        self.scheduling = config.ensemble_scheduling or EnsembleScheduling()
        self._repo: "ModelRepository | None" = None

    def set_repository(self, repo: "ModelRepository") -> None:
        """Provide access to the model repository so steps can be resolved."""
        self._repo = repo

    def schedule(self, requests: List[InferenceRequest]) -> List[List[InferenceRequest]]:
        # Each ensemble request is executed independently in this demo.
        return [[req] for req in requests]

    def execute(self, request: InferenceRequest) -> Dict[str, np.ndarray]:
        """Execute the ensemble chain for a single request."""
        if self._repo is None:
            raise RuntimeError("EnsembleScheduler requires a ModelRepository")
        pool: Dict[str, np.ndarray] = dict(request.inputs)
        # Steps are assumed to be topologically sorted as in real Triton configs.
        for step in self.scheduling.step:
            submodel = self._repo.get(step.model_name)
            step_inputs: Dict[str, np.ndarray] = {}
            for step_input_name, tensor_name in step.input_map.items():
                if tensor_name not in pool:
                    raise ValueError(
                        f"Ensemble step for {step.model_name} missing tensor: {tensor_name}"
                    )
                step_inputs[step_input_name] = pool[tensor_name]
            step_outputs = submodel.backend.execute(step_inputs, submodel.config)
            for step_output_name, tensor_name in step.output_map.items():
                if step_output_name not in step_outputs:
                    raise ValueError(
                        f"Sub-model {step.model_name} did not produce output: {step_output_name}"
                    )
                pool[tensor_name] = step_outputs[step_output_name]
        # Collect final outputs according to the ensemble model output specs.
        outputs: Dict[str, np.ndarray] = {}
        for spec in self.config.outputs:
            if spec.name not in pool:
                raise ValueError(f"Ensemble did not produce output tensor: {spec.name}")
            outputs[spec.name] = pool[spec.name]
        return outputs
