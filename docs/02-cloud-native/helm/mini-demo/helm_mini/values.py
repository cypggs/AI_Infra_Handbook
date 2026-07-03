"""values 合并 —— Helm 的“深合并”算法。

规则（见正文 5.4）：
  * map：递归合并（同名 key 深合并，不整体替换）。
  * list：**整体替换**（不按下标合并）——这是最易踩的点。
优先级（低 -> 高）：
  subchart values.yaml < parent values.yaml
    < -f extra.yaml < --set < --set-string
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping


def deep_merge(dst: Dict[str, Any], src: Mapping[str, Any]) -> Dict[str, Any]:
    """把 src 深合并进 dst（原地修改并返回）。map 递归；list/标量整体替换。"""
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = deepcopy(v)
    return dst


def merge_values(*layers: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """按优先级从低到高依次合并多层 values，返回最终 values。"""
    result: Dict[str, Any] = {}
    for layer in layers:
        if layer:
            for item in layer:
                if item:
                    deep_merge(result, item)
    return result
