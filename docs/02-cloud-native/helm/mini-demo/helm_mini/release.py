"""Release —— 一次带版本的安装实例（Helm 的“undo log”）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .chart import Chart


class ReleaseStatus(str, Enum):
    PENDING_INSTALL = "pending-install"
    PENDING_UPGRADE = "pending-upgrade"
    PENDING_ROLLBACK = "pending-rollback"
    DEPLOYED = "deployed"
    SUPERSEDED = "superseded"      # 被新版本取代的历史版本
    FAILED = "failed"
    UNINSTALLING = "uninstalling"
    UNINSTALLED = "uninstalled"


@dataclass
class Manifest:
    """一个被渲染出的 K8s 资源（结构化 + 文本两种表示）。"""

    kind: str
    namespace: str
    name: str
    body: Dict[str, Any]           # 结构化清单（三方合并在此操作）
    raw: str                       # 渲染出的 YAML 文本（用于展示/审计）

    @property
    def key(self) -> tuple:
        return (self.kind, self.namespace, self.name)


@dataclass
class Release:
    """对应 Helm 的 release 对象，会被编码进 Secret。"""

    name: str
    namespace: str
    chart: Chart                   # 本次用的 chart（深拷贝，保证历史可回溯）
    config: Dict[str, Any]         # 合并后的 values（即 .Values）
    manifests: List[Manifest]      # 渲染出的资源清单
    manifest_text: str             # 完整渲染文本（= 拼接所有 Manifest.raw，存进 Secret）
    version: int                   # revision 号
    status: ReleaseStatus = ReleaseStatus.PENDING_INSTALL
    info: str = ""                 # 描述/错误信息
    hooks: List[Dict[str, Any]] = field(default_factory=list)
