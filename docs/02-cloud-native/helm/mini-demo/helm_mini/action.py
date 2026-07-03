"""action —— install / upgrade / rollback / uninstall 业务动作。

对应 Helm 的 ``pkg/action``：编排 渲染(engine) + 存储(storage) + 集群(kube)，
并把每次操作的 release 记录成一个 Secret（revision）。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .chart import Chart
from .engine import (ReleaseContext, manifests_to_text, parse_manifest_text,
                     render_chart)
from .kube import KubeClient
from .release import Release, ReleaseStatus
from .storage import Storage
from .values import merge_values


@dataclass
class Configuration:
    """持有 storage / kubeclient，由调用方注入（模拟 pkg/cli.Configuration）。"""

    storage: Storage = field(default_factory=Storage)
    kube: KubeClient = field(default_factory=KubeClient)


class _ActionBase:
    def __init__(self, cfg: Configuration):
        self.cfg = cfg

    # ---- 渲染辅助 ------------------------------------------------------- #
    def _merge(self, chart: Chart, user_values: List[Dict[str, Any]]) -> Dict[str, Any]:
        return merge_values([chart.values], user_values)

    def _render(self, chart: Chart, values: Dict[str, Any], rel: ReleaseContext) -> List:
        return render_chart(chart, values, rel)

    def _new_release(self, name: str, namespace: str, chart: Chart,
                     values: Dict[str, Any], manifests, status: ReleaseStatus,
                     version: int = 0, info: str = "") -> Release:
        return Release(
            name=name,
            namespace=namespace,
            chart=deepcopy(chart),
            config=deepcopy(values),
            manifests=manifests,
            manifest_text=manifests_to_text(manifests),
            version=version,
            status=status,
            info=info,
        )


class Install(_ActionBase):
    def __init__(self, cfg: Configuration, *, wait: bool = True, atomic: bool = False):
        super().__init__(cfg)
        self.wait = wait
        self.atomic = atomic

    def run(self, name: str, chart: Chart, namespace: str = "default",
            values: Optional[List[Dict[str, Any]]] = None) -> Release:
        values = values or []
        merged = self._merge(chart, values)
        rel = ReleaseContext(Name=name, Namespace=namespace, Revision=1, IsInstall=True)
        manifests = self._render(chart, merged, rel)

        release = self._new_release(name, namespace, chart, merged, manifests,
                                    ReleaseStatus.PENDING_INSTALL, version=0)
        # 1) 先写 pending Secret，再 apply（崩溃可追溯）
        self.cfg.storage.create(release)
        release.info = "pending-install recorded"

        try:
            # 2) pre-install hook 略（本 demo 不实现 hook 调度，但保留语义位置）
            actions = self.cfg.kube.create(manifests)
            # 3) wait：本 demo 假设资源立即可用，仅记录语义
            release.info = f"deployed: {', '.join(actions)}"
            release.status = ReleaseStatus.DEPLOYED
            self.cfg.storage.update(release)
        except Exception as e:
            release.status = ReleaseStatus.FAILED
            release.info = f"install failed: {e}"
            self.cfg.storage.update(release)
            if self.atomic:
                self.cfg.kube.delete(manifests)  # 回滚已创建的
            raise
        return release


class Upgrade(_ActionBase):
    def __init__(self, cfg: Configuration, *, wait: bool = True, atomic: bool = True,
                 reset_values: bool = True, reuse_values: bool = False):
        super().__init__(cfg)
        self.wait = wait
        self.atomic = atomic
        self.reset_values = reset_values
        self.reuse_values = reuse_values

    def run(self, name: str, chart: Chart, namespace: str = "default",
            values: Optional[List[Dict[str, Any]]] = None) -> Release:
        values = values or []
        current = self.cfg.storage.deployed(name)
        if current is None:
            raise RuntimeError(f"no deployed release named {name!r}")

        # values 合并：reuse_values 时以旧 config 为底再叠加本次（见正文 4.3）
        if self.reuse_values and not self.reset_values:
            merged = merge_values([chart.values], [current.config], values)
        else:
            merged = self._merge(chart, values)

        rel = ReleaseContext(Name=name, Namespace=namespace,
                             Revision=current.version + 1, IsUpgrade=True)
        new_manifests = self._render(chart, merged, rel)
        old_manifests = current.manifests  # 上一版渲染清单 = old

        release = self._new_release(name, namespace, chart, merged, new_manifests,
                                    ReleaseStatus.PENDING_UPGRADE, version=0)
        self.cfg.storage.create(release)

        try:
            actions = self.cfg.kube.update(old_manifests, new_manifests)
            # 旧版 -> superseded，新版 -> deployed
            current.status = ReleaseStatus.SUPERSEDED
            current.info = f"superseded by revision {release.version}"
            self.cfg.storage.update(current)
            release.status = ReleaseStatus.DEPLOYED
            release.info = f"upgraded: {', '.join(actions)}"
            self.cfg.storage.update(release)
        except Exception as e:
            release.status = ReleaseStatus.FAILED
            release.info = f"upgrade failed: {e}"
            self.cfg.storage.update(release)
            if self.atomic:
                # 自动回滚：把 old 重新 apply
                self.cfg.kube.update([], old_manifests)
                # 新建一个 rollback revision（语义占位）
                rollback_release = self._new_release(
                    name, namespace, current.chart, current.config, old_manifests,
                    ReleaseStatus.DEPLOYED, version=0,
                    info=f"atomic rollback to revision {current.version}")
                self.cfg.storage.create(rollback_release)
            raise
        return release


class Rollback(_ActionBase):
    def __init__(self, cfg: Configuration, *, wait: bool = True):
        super().__init__(cfg)
        self.wait = wait

    def run(self, name: str, target_revision: int, namespace: str = "default") -> Release:
        current = self.cfg.storage.deployed(name)
        target = self.cfg.storage.get(name, target_revision)
        if current is None or target is None:
            raise RuntimeError(f"cannot rollback: missing release/revision")

        rel = ReleaseContext(Name=name, Namespace=namespace,
                             Revision=current.version + 1, IsUpgrade=False)
        # rollback 用目标版的清单做一次 upgrade（三方合并）
        old_manifests = current.manifests
        target_manifests = target.manifests

        release = self._new_release(name, namespace, target.chart, target.config,
                                    target_manifests, ReleaseStatus.PENDING_ROLLBACK, version=0)
        self.cfg.storage.create(release)

        actions = self.cfg.kube.update(old_manifests, target_manifests)
        current.status = ReleaseStatus.SUPERSEDED
        current.info = f"superseded by rollback to revision {target_revision}"
        self.cfg.storage.update(current)

        release.status = ReleaseStatus.DEPLOYED
        release.info = f"rolled back to revision {target_revision}: {', '.join(actions)}"
        self.cfg.storage.update(release)
        return release


class Uninstall(_ActionBase):
    def __init__(self, cfg: Configuration, *, keep_history: bool = False):
        super().__init__(cfg)
        self.keep_history = keep_history

    def run(self, name: str) -> Release:
        current = self.cfg.storage.deployed(name) or self.cfg.storage.latest(name)
        if current is None:
            raise RuntimeError(f"no release named {name!r}")

        current.status = ReleaseStatus.UNINSTALLING
        current.info = "uninstalling"
        self.cfg.storage.update(current)

        actions = self.cfg.kube.delete(current.manifests)
        current.status = ReleaseStatus.UNINSTALLED
        current.info = f"uninstalled: {', '.join(actions)}"
        self.cfg.storage.update(current)

        if not self.keep_history:
            self.cfg.storage.delete_release(name, keep_history=False)
        return current
