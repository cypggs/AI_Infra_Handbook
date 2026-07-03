"""渲染：Chart + values + Release 上下文 -> 一组 Manifest。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List

from .chart import Chart
from .release import Manifest
from .template import Engine
from .yaml_lite import load_all


@dataclass
class ReleaseContext:
    """模板里 ``.Release`` 能访问到的字段（部分）。"""

    Name: str
    Namespace: str
    Revision: int = 1
    IsInstall: bool = True
    IsUpgrade: bool = False
    Service: str = "Helm"


# 不作为输出清单渲染的模板文件名前缀/路径
_SKIP_PREFIX = ("_",)
_SKIP_FILES = ("NOTES.txt",)


def _build_ctx(chart: Chart, values: Dict[str, Any], rel: ReleaseContext) -> dict:
    return {
        "Values": values,
        "Release": {
            "Name": rel.Name,
            "Namespace": rel.Namespace,
            "Revision": rel.Revision,
            "IsInstall": rel.IsInstall,
            "IsUpgrade": rel.IsUpgrade,
            "Service": rel.Service,
        },
        "Chart": {
            "Name": chart.metadata.name,
            "Version": chart.metadata.version,
            "AppVersion": chart.metadata.appVersion,
            "APIVersion": chart.metadata.apiVersion,
        },
    }


def _is_output_template(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    if base in _SKIP_FILES:
        return False
    if "/tests/" in name or name.startswith("tests/"):
        return False
    if base.startswith(_SKIP_PREFIX):
        return False
    return True


def render_chart(chart: Chart, values: Dict[str, Any], rel: ReleaseContext) -> List[Manifest]:
    """渲染 chart 的所有输出模板，返回 Manifest 列表（已按文件拆分多文档）。"""
    engine = Engine()
    ctx = _build_ctx(chart, values, rel)

    rendered_chunks: List[str] = []
    for name, text in chart.templates:
        if not _is_output_template(name):
            # 仍要过一遍 engine 以收集其 define（_helpers.tpl）
            engine.render(text, ctx)
            continue
        out = engine.render(text, ctx)
        if out.strip():
            rendered_chunks.append(out)

    manifests: List[Manifest] = []
    for chunk in rendered_chunks:
        for body in load_all(chunk):
            if not isinstance(body, dict) or "kind" not in body:
                continue
            meta = body.get("metadata", {}) or {}
            ns = meta.get("namespace") or rel.Namespace
            name = meta.get("name", "")
            # 重新序列化单文档文本（保证 raw 是该资源自身的 YAML）
            from .yaml_lite import dump
            manifests.append(Manifest(
                kind=body.get("kind", ""),
                namespace=ns,
                name=name,
                body=body,
                raw=dump(body),
            ))
    return manifests


def manifests_to_text(manifests: List[Manifest]) -> str:
    """拼接所有 manifest 文本，存进 release Secret。"""
    return "\n---\n".join(m.raw for m in manifests)


def parse_manifest_text(text: str) -> List[Manifest]:
    """从 release Secret 的 manifest_text 还原 Manifest 列表（rollback 用）。"""
    out: List[Manifest] = []
    for body in load_all(text):
        if not isinstance(body, dict) or "kind" not in body:
            continue
        meta = body.get("metadata", {}) or {}
        from .yaml_lite import dump
        out.append(Manifest(
            kind=body.get("kind", ""),
            namespace=meta.get("namespace", ""),
            name=meta.get("name", ""),
            body=body,
            raw=dump(body),
        ))
    return out
