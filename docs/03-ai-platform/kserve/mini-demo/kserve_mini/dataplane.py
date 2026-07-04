"""Fake model server data plane supporting V1, V2 and OpenAI protocols."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class Request:
    protocol: str  # "v1", "v2", "openai"
    path: str
    body: dict[str, Any]


@dataclass
class Response:
    status_code: int
    body: dict[str, Any]


class FakeModelServer:
    """A deterministic fake model server.

    It supports three protocols:
    - v1: POST /v1/models/<name>:predict
    - v2: POST /v2/models/<name>/infer
    - openai: POST /openai/v1/chat/completions
    """

    def __init__(self, name: str, runtime_name: str) -> None:
        self.name = name
        self.runtime_name = runtime_name
        self.ready = True

    def predict(self, request: Request) -> Response:
        if not self.ready:
            return Response(status_code=503, body={"error": "model not ready"})

        if request.protocol == "v1":
            return self._v1_predict(request)
        if request.protocol == "v2":
            return self._v2_predict(request)
        if request.protocol == "openai":
            return self._openai_predict(request)
        return Response(status_code=400, body={"error": f"unsupported protocol {request.protocol}"})

    def _v1_predict(self, request: Request) -> Response:
        instances = request.body.get("instances", [])
        return Response(
            status_code=200,
            body={
                "predictions": [[float(i), float(i) + 1.0] for i in range(len(instances))],
                "model": self.name,
                "runtime": self.runtime_name,
            },
        )

    def _v2_predict(self, request: Request) -> Response:
        inputs = request.body.get("inputs", [])
        return Response(
            status_code=200,
            body={
                "model_name": self.name,
                "outputs": [
                    {
                        "name": "output",
                        "shape": [1, 2],
                        "datatype": "FP32",
                        "data": [0.0, 1.0],
                    }
                    for _ in inputs
                ],
                "runtime": self.runtime_name,
            },
        )

    def _openai_predict(self, request: Request) -> Response:
        messages = request.body.get("messages", [])
        content = " ".join(str(m.get("content", "")) for m in messages)
        return Response(
            status_code=200,
            body={
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "model": self.name,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": f"Echo: {content}"},
                        "finish_reason": "stop",
                    }
                ],
                "runtime": self.runtime_name,
            },
        )
