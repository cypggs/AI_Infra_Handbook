"""一个 fake OCI registry，预置若干示例镜像（单架构 + 多架构）。

对应真实的 registry（Docker Hub / Harbor），但镜像内容是构造好的示例数据，
用于演示 pull、内容寻址去重、多架构选择。
"""
from __future__ import annotations

from .image import Image, ImageConfig, Layer, ManifestEntry, ManifestList


def _alpine_py_image() -> Image:
    base = Layer(files={
        "/etc/os-release": "Alpine v3.20",
        "/bin/sh": "#!/bin/sh shim",
        "/lib/libc.so": "musl",
    })
    pkg = Layer(
        files={
            "/usr/bin/python3": "#!/usr/bin/env python3",
            "/usr/lib/python3.12/__init__.py": "",
        },
        parent=base.digest,
    )
    return Image(
        config=ImageConfig(
            entrypoint=["python3"],
            cmd=["-c", "print('hello')"],
            env=["PYTHON_VERSION=3.12", "PATH=/usr/bin"],
        ),
        layers=[base, pkg],
    )


def _nginx_image() -> Image:
    base = Layer(files={"/etc/os-release": "Debian 12", "/bin/sh": "#!/bin/sh shim"})
    app = Layer(
        files={
            "/usr/sbin/nginx": "<nginx binary>",
            "/etc/nginx/nginx.conf": "daemon off;",
        },
        parent=base.digest,
    )
    return Image(
        config=ImageConfig(
            user="101:101",
            entrypoint=["/usr/sbin/nginx"],
            cmd=["-g", "daemon off;"],
            env=["NGINX_VERSION=1.27"],
            exposed_ports=["80/tcp"],
        ),
        layers=[base, app],
    )


def _ai_server_for_arch(arch: str) -> Image:
    base = Layer(files={"/etc/os-release": f"Linux/{arch}", "/bin/sh": f"{arch}-shim"})
    app = Layer(
        files={
            "/app/server.py": "import socket; print('serving')",
            "/model/index.json": "weights-manifest",
        },
        parent=base.digest,
    )
    return Image(
        config=ImageConfig(
            user="10001:10001",
            entrypoint=["python3"],
            cmd=["/app/server.py"],
            env=["CUDA_VERSION=12.4"],
        ),
        layers=[base, app],
    )


def build_registry() -> dict[str, Image | ManifestList]:
    reg: dict[str, Image | ManifestList] = {}
    reg["docker.io/library/alpine-py:3.12"] = _alpine_py_image()
    reg["docker.io/library/nginx:1.27"] = _nginx_image()
    reg["myreg/ai-server:v1"] = ManifestList(
        entries=[
            ManifestEntry("linux/amd64", _ai_server_for_arch("amd64")),
            ManifestEntry("linux/arm64", _ai_server_for_arch("arm64")),
        ]
    )
    return reg


class Registry:
    def __init__(self) -> None:
        self._store = build_registry()

    def resolve(self, ref: str) -> Image | ManifestList:
        if ref not in self._store:
            raise KeyError(f"unknown ref {ref}; known: {list(self._store)}")
        return self._store[ref]

    def refs(self) -> list[str]:
        return list(self._store.keys())
