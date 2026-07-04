"""Ingress / Gateway simulation with canary traffic split."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from kserve_mini.dataplane import FakeModelServer, Request, Response


@dataclass
class Route:
    path: str
    protocol: str


class Gateway:
    """Routes external requests to model-server revisions.

    Supports host-based routing and weighted canary splitting between a
    `stable` and a `canary` revision.
    """

    def __init__(self, host: str) -> None:
        self.host = host
        self.routes: list[Route] = [
            Route(path="/v1/models/:predict", protocol="v1"),
            Route(path="/v2/models/:infer", protocol="v2"),
            Route(path="/openai/v1/chat/completions", protocol="openai"),
        ]
        self.stable: FakeModelServer | None = None
        self.canary: FakeModelServer | None = None
        self.canary_percent: int = 0

    def set_stable(self, server: FakeModelServer) -> None:
        self.stable = server

    def set_canary(self, server: FakeModelServer | None, percent: int) -> None:
        self.canary = server
        self.canary_percent = max(0, min(100, percent))

    def route(self, protocol: str, body: dict[str, Any]) -> Response:
        if self.stable is None:
            return Response(status_code=503, body={"error": "no stable backend"})

        request = Request(protocol=protocol, path=self._path_for(protocol), body=body)

        # Weighted random canary split.
        if self.canary is not None and random.randint(1, 100) <= self.canary_percent:
            return self.canary.predict(request)
        return self.stable.predict(request)

    def _path_for(self, protocol: str) -> str:
        if protocol == "v1":
            return "/v1/models/model:predict"
        if protocol == "v2":
            return "/v2/models/model/infer"
        return "/openai/v1/chat/completions"

    @property
    def weights(self) -> dict[str, int]:
        return {
            "stable": 100 - self.canary_percent,
            "canary": self.canary_percent,
        }
