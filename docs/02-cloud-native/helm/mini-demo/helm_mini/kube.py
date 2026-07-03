"""kube client + 三方合并 Patch。

三方合并是 Helm v3 升级安全性的核心（见正文 3.4）：升级时同时参考
  ① 上一版清单（old，chart 上次渲染的）
  ② 集群现状（live）
  ③ 本次清单（new，chart 这次渲染的）
原则：chart 在 old->new 之间没改的字段，若 live 与 old 不同（=人工改过），保留 live；
      chart 改了的字段，用 new；chart 删除的字段，若 live 未被人工改过，则删除。

本实现处理 dict 递归、scalar/list 用“old==new 则取 live 否则取 new”规则。
真实 Helm 用 K8s strategic-merge-patch（list 按 merge key 合并），本 demo 把 list 简化为整体替换
（见 07-mini-demo.md 差异表）——对“replicas 不被覆盖”这类教学用例完全够用。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .release import Manifest
from .yaml_lite import MISSING, dump, load_all


# --------------------------------------------------------------------------- #
# 三方合并
# --------------------------------------------------------------------------- #
def three_way_merge(old: Dict[str, Any], live: Dict[str, Any],
                    new: Dict[str, Any]) -> Dict[str, Any]:
    """返回合并后的对象。old/live/new 都是 dict（缺失传 {}）。"""
    # 非 dict 上下文：old==new 则保留 live，否则用 new
    if not (isinstance(new, dict) and isinstance(old, dict) and isinstance(live, dict)):
        if old == new:
            return deepcopy(live) if live is not MISSING else deepcopy(new)
        return deepcopy(new)

    result: Dict[str, Any] = {}
    keys = set(old) | set(new) | set(live)
    for k in keys:
        o = old.get(k, MISSING)
        n = new.get(k, MISSING)
        l = live.get(k, MISSING)

        if n is MISSING:
            # chart 在 new 中删除了该字段
            if l is not MISSING and (o is MISSING or o != l):
                # live 有且（被人工改过 / 人工新增）-> 保留
                result[k] = deepcopy(l)
            # 否则（live 未改/不存在）-> 删除（不写入 result）
            continue

        # n 存在
        if o is MISSING:
            # chart 在 new 中新增的字段 -> 用 new（递归处理嵌套）
            if isinstance(n, dict) and isinstance(l, dict):
                result[k] = three_way_merge({}, l, n)
            else:
                result[k] = deepcopy(n)
            continue

        if o == n:
            # chart 没改这一项 -> 保留 live（若存在），否则 new
            if l is not MISSING:
                if isinstance(n, dict) and isinstance(l, dict):
                    result[k] = three_way_merge(o, l, n)
                else:
                    result[k] = deepcopy(l)
            else:
                result[k] = deepcopy(n)
        else:
            # chart 改了 -> 用 new，但递归保留嵌套里的人工改动
            if isinstance(n, dict) and isinstance(l, dict):
                result[k] = three_way_merge(o, l, n)
            else:
                result[k] = deepcopy(n)
    return result


# --------------------------------------------------------------------------- #
# KubeClient —— 与 apiserver 交互的模拟
# --------------------------------------------------------------------------- #
class KubeClient:
    """模拟一个集群：``cluster`` 是 identity -> live manifest(dict) 的映射。"""

    KEEP_POLICY = "helm.sh/resource-policy"

    def __init__(self):
        self.cluster: Dict[tuple, Dict[str, Any]] = {}
        self.events: List[str] = []

    # ---- 帮助函数 ------------------------------------------------------- #
    @staticmethod
    def _id_of(body: Dict[str, Any], default_ns: str) -> tuple:
        meta = body.get("metadata", {}) or {}
        return (body.get("kind", ""), meta.get("namespace", default_ns) or default_ns,
                meta.get("name", ""))

    def _keep(self, body: Dict[str, Any]) -> bool:
        annotations = (body.get("metadata", {}) or {}).get("annotations", {}) or {}
        return annotations.get(self.KEEP_POLICY) == "keep"

    # ---- install: 创建 -------------------------------------------------- #
    def create(self, manifests: List[Manifest]) -> List[str]:
        actions = []
        for m in manifests:
            if m.key in self.cluster:
                raise RuntimeError(f"resource already exists: {m.key}")
            self.cluster[m.key] = deepcopy(m.body)
            actions.append(f"created {m.kind}/{m.name}")
            self.events.append(f"create {m.key}")
        return actions

    # ---- upgrade: 三方合并 ---------------------------------------------- #
    def update(self, old_manifests: List[Manifest], new_manifests: List[Manifest]) -> List[str]:
        old_by_id = {m.key: m.body for m in old_manifests}
        new_by_id = {m.key: m.body for m in new_manifests}
        actions: List[str] = []

        # 1) 三方合并 / 新建
        for m in new_manifests:
            live = self.cluster.get(m.key)
            old = old_by_id.get(m.key, {})
            if m.key not in self.cluster:
                # chart 新增的资源 -> 创建
                self.cluster[m.key] = deepcopy(m.body)
                actions.append(f"created {m.kind}/{m.name}")
                self.events.append(f"create {m.key}")
            else:
                merged = three_way_merge(old or {}, live or {}, m.body)
                self.cluster[m.key] = merged
                actions.append(f"patched {m.kind}/{m.name}")
                self.events.append(f"patch {m.key}")

        # 2) chart 删除的资源
        for key, old_body in old_by_id.items():
            if key in new_by_id:
                continue
            if key in self.cluster and not self._keep(self.cluster[key]):
                del self.cluster[key]
                actions.append(f"deleted {key[0]}/{key[2]}")
                self.events.append(f"delete {key}")
            elif key in self.cluster:
                actions.append(f"kept (resource-policy=keep) {key[0]}/{key[2]}")
        return actions

    # ---- uninstall: 删除 ------------------------------------------------ #
    def delete(self, manifests: List[Manifest]) -> List[str]:
        actions = []
        # 逆序删除（workloads 先于依赖），保持与 Helm 一致
        for m in reversed(manifests):
            if m.key in self.cluster:
                if self._keep(self.cluster[m.key]):
                    actions.append(f"kept (resource-policy=keep) {m.kind}/{m.name}")
                    continue
                del self.cluster[m.key]
                actions.append(f"deleted {m.kind}/{m.name}")
                self.events.append(f"delete {m.key}")
        return actions

    # ---- 调试/模拟人工操作 ---------------------------------------------- #
    def live(self, kind: str, namespace: str, name: str) -> Dict[str, Any]:
        # 返回 deepcopy 快照，避免外部别名导致“读到的值随集群后续变化而漂移”
        body = self.cluster.get((kind, namespace, name))
        return deepcopy(body) if body is not None else {}

    def apply_manual_change(self, kind: str, namespace: str, name: str,
                            path: List[str], value: Any) -> None:
        """模拟 kubectl 手动改字段（如 scale）。供演示三方合并用。"""
        body = self.cluster[(kind, namespace, name)]
        cur = body
        for p in path[:-1]:
            cur = cur[p]
        cur[path[-1]] = value
        self.events.append(f"manual-edit {(kind, namespace, name)} set {'.'.join(path)}={value}")
