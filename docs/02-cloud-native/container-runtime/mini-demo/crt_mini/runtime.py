"""OCI Runtime（mini-runc）：基于 namespace + cgroup + rootfs 的 create/start/exec 生命周期。

对应 opencontainers/runc 的 libcontainer：
- create：建 namespace、设 cgroup、挂 rootfs（pivot_root），建容器主进程但不 exec（state=created）；
- start：exec 用户进程（容器 PID 1），进入 running；
- exec：setns 进容器再起进程；
- stop/delete：终止与清理。

容器内的"运行时交互"（写文件、用内存、用 CPU）也在此暴露，用于演示 COW/OOM/throttle。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .cgroup import Cgroup
from .namespace import NamespaceSet


@dataclass
class OCIConfig:
    """OCI runtime-spec config.json 的子集。"""

    args: list[str]
    env: list[str] = field(default_factory=list)
    user: str = "root"
    cwd: str = "/"
    hostname: str = "container"
    cpu_quota_us: int = -1
    memory_max: int = -1
    pids_max: int = -1
    capabilities_drop: list[str] = field(default_factory=lambda: ["ALL"])
    readonly_rootfs: bool = False
    snapshot_key: str = ""  # rootfs 来源（snapshotter 的 active 快照）


class Container:
    """一个 OCI 容器，拥有真实的 create→start→running→stopped 生命周期。"""

    def __init__(
        self,
        id: str,
        config: OCIConfig,
        snapshotter,
        observer: list | None = None,
    ) -> None:
        self.id = id
        self.config = config
        self.snapshotter = snapshotter
        self.observer = observer if observer is not None else []
        self.namespaces = NamespaceSet.isolated()
        self.cgroup = Cgroup(
            name=f"/{id}",
            cpu_quota_us=config.cpu_quota_us,
            memory_max=config.memory_max,
            pids_max=config.pids_max,
        )
        self.state = "creating"
        self.pid_ns_counter = 0
        self.exit_code: Optional[int] = None
        self.rootfs: dict[str, str] = {}

    # ---------- 生命周期（对应 runc create / start / exec / kill / delete） ----------
    def create(self) -> None:
        """阶段一：建 namespace/cgroup/mount，但不 exec 用户进程。"""
        self.rootfs = dict(self.snapshotter.merged(self.config.snapshot_key))
        self.cgroup.acquire_pid()  # init 进程槽位
        self.pid_ns_counter = 1  # 容器内 PID 1 留给入口进程
        # 模拟 pivot_root + capabilities drop + seccomp（这里只记账）
        self._emit("create", {"rootfs_files": sorted(self.rootfs), "drop_caps": self.config.capabilities_drop})
        self.state = "created"

    def start(self) -> None:
        """阶段二：exec 用户进程 -> 容器内 PID 1，进入 running。"""
        if self.state != "created":
            raise RuntimeError(f"cannot start from state {self.state}")
        self.state = "running"
        self.namespaces.pid.add(("process", 1, self.config.args))
        self.namespaces.uts.add(self.config.hostname)
        self._emit("start", {"pid": 1, "args": self.config.args})

    def exec(self, args: list[str]) -> dict:
        """setns 进容器再起一个进程（对应 runc exec / kubectl exec）。"""
        if self.state != "running":
            raise RuntimeError("container not running")
        ok = self.cgroup.acquire_pid()
        if ok != "ok":
            self._emit("exec-rejected", {"reason": ok})
            return {"pid": None, "reason": ok}
        self.pid_ns_counter += 1
        pid = self.pid_ns_counter
        self.namespaces.pid.add(("process", pid, args))
        self._emit("exec", {"pid": pid, "args": args})
        return {"pid": pid}

    def stop(self, signal: str = "TERM") -> None:
        self.state = "stopped"
        self.exit_code = 0 if signal == "TERM" else 137
        self._emit("stop", {"signal": signal, "exit_code": self.exit_code})

    def delete(self) -> None:
        self.snapshotter.remove(self.config.snapshot_key)
        self.state = "deleted"
        self._emit("delete", {})

    # ---------- 容器内运行时交互（演示 COW / OOM / throttle） ----------
    def write_file(self, path: str, content: str) -> dict:
        """容器内进程写 rootfs（演示 overlayfs copy-on-write）。"""
        if self.config.readonly_rootfs:
            return {"error": "read-only rootfs"}
        cow = self.snapshotter.write(self.config.snapshot_key, path, content)
        self.rootfs[path] = content
        self._emit("write", {"path": path, **cow})
        return cow

    def use_memory(self, bytes_: int) -> str:
        """容器内进程分配内存（演示 memory.max + OOMKill）。"""
        result = self.cgroup.consume_memory(bytes_)
        self._emit("memory", {"bytes": bytes_, "result": result})
        if result == "oom":
            self.state = "stopped"
            self.exit_code = 137
            self._emit("oom-kill", {})
        return result

    def use_cpu(self, us: int) -> str:
        """容器内进程用 CPU（演示 CFS quota + throttle）。"""
        result = self.cgroup.tick(us)
        self._emit("cpu", {"us": us, "result": result})
        return result

    # ---------- 内部 ----------
    def _emit(self, event: str, data: dict) -> None:
        self.observer.append({"container": self.id, "event": event, **data})
