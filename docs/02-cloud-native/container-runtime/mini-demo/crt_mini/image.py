"""OCI 镜像概念：层（Layer）、镜像配置（ImageConfig）、镜像（Image）、多架构清单（ManifestList）。

对应 OCI Image Specification 的核心数据结构，但为教学做了简化（层内容用 path->content
字典表示，而非真实 tar 归档）。所有内容用 SHA256 摘要做内容寻址，模拟真实镜像的去重与校验。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional


def digest(*parts: object) -> str:
    """对若干可序列化的 part 计算确定性的内容摘要（sha256，截短为 16 位 hex 以便阅读）。"""
    h = hashlib.sha256()
    for p in parts:
        h.update(repr(p).encode("utf-8"))
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()[:16]


@dataclass
class Layer:
    """一个文件系统层（增量）。files: path -> content（模拟解包后的层内容）。"""

    files: dict[str, str] = field(default_factory=dict)
    parent: Optional[str] = None  # 父层 digest（构建快照链用）
    digest: str = ""

    def __post_init__(self) -> None:
        # diff_id（未压缩摘要）由 (parent, files) 内容寻址得到
        self.digest = digest(self.parent, sorted(self.files.items()))


@dataclass
class ImageConfig:
    """镜像配置（OCI image config 的子集）。"""

    user: str = "root"
    env: list[str] = field(default_factory=list)
    entrypoint: list[str] = field(default_factory=list)
    cmd: list[str] = field(default_factory=list)
    working_dir: str = "/"
    exposed_ports: list[str] = field(default_factory=list)

    @property
    def digest(self) -> str:
        return digest(sorted(vars(self).items()))


@dataclass
class Image:
    """一个镜像 = 配置 + 有序的层列表。"""

    config: ImageConfig
    layers: list[Layer]

    @property
    def manifest(self) -> dict:
        """单架构 manifest：指向 config + 各层（按 digest）。"""
        return {
            "config": self.config.digest,
            "layers": [layer.digest for layer in self.layers],
        }


@dataclass
class ManifestEntry:
    """manifest list 中的一项：某架构对应的镜像。"""

    platform: str  # 如 "linux/amd64"
    image: Image


@dataclass
class ManifestList:
    """多架构镜像索引（OCI image index）。"""

    entries: list[ManifestEntry]

    def select(self, platform: str) -> Image:
        """按平台选择对应的子镜像（真实流程是先选 manifest 再展开）。"""
        for e in self.entries:
            if e.platform == platform:
                return e.image
        raise KeyError(f"no manifest for platform {platform}")

    @property
    def platforms(self) -> list[str]:
        return [e.platform for e in self.entries]
