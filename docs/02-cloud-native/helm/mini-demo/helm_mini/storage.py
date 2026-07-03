"""Release 存储 —— 模拟 Helm v3 把每个 revision 存成 namespace 内的 Secret。

真实 Helm 里 Secret 名为 ``sh.helm.release.v1.<release>.v<revision>``，
data.release 字段是 gzip+base64 的 protobuf。这里用内存 dict 模拟，
但保留 key 命名与“每个 revision 一个 Secret”的语义，并支持 ``history-max``。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .release import Release, ReleaseStatus


class SecretDriver:
    """模拟 Secret 存储：key -> Release。"""

    TYPE = "helm.sh/release.v1"
    PREFIX = "sh.helm.release.v1"

    def __init__(self):
        self._store: Dict[str, Release] = {}

    @staticmethod
    def secret_name(release_name: str, version: int) -> str:
        return f"{SecretDriver.PREFIX}.{release_name}.v{version}"

    def create(self, key: str, rel: Release) -> None:
        if key in self._store:
            raise ValueError(f"release secret already exists: {key}")
        self._store[key] = rel

    def update(self, key: str, rel: Release) -> None:
        if key not in self._store:
            raise KeyError(f"no such release secret: {key}")
        self._store[key] = rel

    def delete(self, key: str) -> Release:
        return self._store.pop(key, None)

    def get(self, key: str) -> Optional[Release]:
        return self._store.get(key)

    def keys(self):
        return list(self._store.keys())


class Storage:
    """在 driver 之上提供 release 级别的 CRUD + history-max 清理。"""

    def __init__(self, driver: Optional[SecretDriver] = None, history_max: int = 10):
        self.driver = driver or SecretDriver()
        self.history_max = history_max

    # ---- 基本读写 ------------------------------------------------------- #
    def create(self, rel: Release) -> Release:
        rel.version = self._next_version(rel.name)
        key = SecretDriver.secret_name(rel.name, rel.version)
        self.driver.create(key, rel)
        self._enforce_history_max(rel.name)
        return rel

    def update(self, rel: Release) -> Release:
        key = SecretDriver.secret_name(rel.name, rel.version)
        self.driver.update(key, rel)
        return rel

    def get(self, name: str, version: int) -> Optional[Release]:
        return self.driver.get(SecretDriver.secret_name(name, version))

    # ---- 派生查询 ------------------------------------------------------- #
    def revisions(self, name: str) -> List[Release]:
        revs = [
            self.driver.get(k) for k in self.driver.keys()
            if k.startswith(f"{SecretDriver.PREFIX}.{name}.v")
        ]
        return sorted([r for r in revs if r], key=lambda r: r.version)

    def history(self, name: str) -> List[Release]:
        return self.revisions(name)

    def deployed(self, name: str) -> Optional[Release]:
        for r in reversed(self.revisions(name)):
            if r.status == ReleaseStatus.DEPLOYED:
                return r
        return None

    def latest(self, name: str) -> Optional[Release]:
        revs = self.revisions(name)
        return revs[-1] if revs else None

    def delete_release(self, name: str, keep_history: bool = False) -> List[Release]:
        revs = self.revisions(name)
        if not keep_history:
            for r in revs:
                self.driver.delete(SecretDriver.secret_name(name, r.version))
        return revs

    # ---- 内部 ----------------------------------------------------------- #
    def _next_version(self, name: str) -> int:
        revs = self.revisions(name)
        return (revs[-1].version + 1) if revs else 1

    def _enforce_history_max(self, name: str) -> None:
        if self.history_max <= 0:
            return
        revs = self.revisions(name)
        # 保留最新 N 个；被挤出的 SUPERSEDED 直接删
        for r in revs[: len(revs) - self.history_max]:
            if r.status == ReleaseStatus.SUPERSEDED:
                self.driver.delete(SecretDriver.secret_name(name, r.version))
