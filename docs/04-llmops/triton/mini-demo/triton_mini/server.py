"""Server entry point for the Mini Triton demo."""
from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List

import numpy as np

from .backend import BaseBackend
from .ensemble import EnsembleScheduler
from .metrics import MetricsCollector
from .model_repository import Model, ModelRepository
from .scheduler import InferenceRequest, Scheduler


class TritonServer:
    """A CPU-runnable Triton-style inference server."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.repository = ModelRepository(repo_path)
        self.metrics = MetricsCollector()

    def load(self) -> "TritonServer":
        """Load all models from the repository."""
        self.repository.load()
        for model in self.repository.models.values():
            if isinstance(model.scheduler, EnsembleScheduler):
                model.scheduler.set_repository(self.repository)
        return self

    def infer(self, model_name: str, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Run a single inference request."""
        results = self.infer_batch(model_name, [inputs])
        return results[0]

    def infer_batch(
        self, model_name: str, inputs_list: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        """Run a batch of inference requests and return individual outputs."""
        model = self.repository.get(model_name)
        requests = [
            InferenceRequest(request_id=f"{model_name}-{i}", model_name=model_name, inputs=inputs)
            for i, inputs in enumerate(inputs_list)
        ]
        self._execute_requests(model, requests)
        return [req.outputs for req in requests]

    def _execute_requests(self, model: Model, requests: List[InferenceRequest]) -> None:
        start = time.perf_counter()
        if isinstance(model.scheduler, EnsembleScheduler):
            for req in requests:
                req.outputs = model.scheduler.execute(req)
        else:
            batches = model.scheduler.schedule(requests)
            for batch in batches:
                self._execute_batch(model, batch)
        elapsed_us = (time.perf_counter() - start) * 1e6
        for req in requests:
            self.metrics.record_request(model.name, req.batch_size, elapsed_us / max(len(requests), 1))

    def _execute_batch(self, model: Model, batch: List[InferenceRequest]) -> None:
        batched_inputs: Dict[str, np.ndarray] = {}
        for name in batch[0].inputs:
            batched_inputs[name] = np.concatenate([req.inputs[name] for req in batch], axis=0)
        outputs = model.backend.execute(batched_inputs, model.config)
        batch_size = len(batch)
        for idx, req in enumerate(batch):
            req.outputs = {
                name: self._slice_batch(outputs[name], idx, batch_size) for name in outputs
            }

    @staticmethod
    def _slice_batch(array: np.ndarray, idx: int, batch_size: int) -> np.ndarray:
        if batch_size == 1:
            return array
        return array[idx : idx + 1]

    def status(self) -> Dict[str, Any]:
        return {
            "repo": str(self.repository.repo_path),
            "models": self.repository.list_models(),
        }


# ---------------------------------------------------------------------------
# Minimal HTTP frontend (educational, not production-ready).
# ---------------------------------------------------------------------------


class _TritonHTTPHandler(BaseHTTPRequestHandler):
    server: "TritonHTTPServer"  # type: ignore[misc]

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default access logs to keep demo output clean.
        pass

    def do_GET(self) -> None:
        if self.path == "/v2/health/ready":
            self._send_json({"ready": True})
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(self.server.triton.metrics.report().encode())
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        import re

        match = re.match(r"/v2/models/([^/]+)/infer", self.path)
        if not match:
            self._send_json({"error": "unsupported endpoint"}, 404)
            return
        model_name = match.group(1)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
            inputs = self._deserialize_inputs(payload.get("inputs", []))
            outputs = self.server.triton.infer(model_name, inputs)
            self._send_json({"outputs": self._serialize_outputs(outputs)})
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, 500)

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    @staticmethod
    def _deserialize_inputs(inputs: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
        result: Dict[str, np.ndarray] = {}
        for item in inputs:
            name = item["name"]
            shape = item["shape"]
            datatype = item["datatype"]
            data = item["data"]
            dtype = _datatype_to_dtype(datatype)
            result[name] = np.array(data, dtype=dtype).reshape(shape)
        return result

    @staticmethod
    def _serialize_outputs(outputs: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "shape": list(arr.shape),
                "datatype": _dtype_to_datatype(arr.dtype),
                "data": arr.tolist(),
            }
            for name, arr in outputs.items()
        ]


class TritonHTTPServer(HTTPServer):
    """HTTP wrapper around `TritonServer`."""

    def __init__(self, triton: TritonServer, host: str = "127.0.0.1", port: int = 8000) -> None:
        super().__init__((host, port), _TritonHTTPHandler)
        self.triton = triton


def _datatype_to_dtype(datatype: str) -> np.dtype:
    mapping = {
        "BOOL": np.bool_,
        "UINT8": np.uint8,
        "INT8": np.int8,
        "UINT16": np.uint16,
        "INT16": np.int16,
        "UINT32": np.uint32,
        "INT32": np.int32,
        "UINT64": np.uint64,
        "INT64": np.int64,
        "FP16": np.float16,
        "FP32": np.float32,
        "FP64": np.float64,
        "BYTES": object,
    }
    if datatype not in mapping:
        raise ValueError(f"Unsupported datatype: {datatype}")
    return mapping[datatype]


def _dtype_to_datatype(dtype: np.dtype) -> str:
    mapping = {
        np.bool_: "BOOL",
        np.uint8: "UINT8",
        np.int8: "INT8",
        np.uint16: "UINT16",
        np.int16: "INT16",
        np.uint32: "UINT32",
        np.int32: "INT32",
        np.uint64: "UINT64",
        np.int64: "INT64",
        np.float16: "FP16",
        np.float32: "FP32",
        np.float64: "FP64",
    }
    return mapping.get(dtype.type, "FP32")


def serve_http(triton: TritonServer, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start a blocking HTTP server for the demo."""
    httpd = TritonHTTPServer(triton, host, port)
    print(f"Triton mini HTTP server listening on http://{host}:{port}")
    httpd.serve_forever()
