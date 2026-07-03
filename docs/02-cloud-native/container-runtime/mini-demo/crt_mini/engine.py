"""高层运行时（mini-containerd）：pull → 解包 → snapshot → create → start 的完整链。

对应 containerd 的职责：管理镜像（拉取/解包成 rootfs）、调用低层运行时（Container）
创建并启动容器。PullImage 演示内容寻址去重；run 演示 `docker run` 的全链路。
"""
from __future__ import annotations

from .content import ContentStore
from .image import Image, ManifestList
from .registry import Registry
from .runtime import OCIConfig, Container
from .snapshot import Snapshotter


class HighLevelRuntime:
    def __init__(self, registry: Registry, observer: list | None = None) -> None:
        self.registry = registry
        self.content = ContentStore()
        self.snapshotter = Snapshotter(self.content)
        self.containers: dict[str, Container] = {}
        self.observer: list = observer if observer is not None else []

    # ---------- 镜像：pull + 解包 ----------
    def pull(self, ref: str, platform: str = "linux/amd64") -> Image:
        """拉取 manifest（多架构则按平台选），把层存入 Content Store（按 digest 去重），
        并解包成 committed 快照（构建父子链）。"""
        target = self.registry.resolve(ref)
        if isinstance(target, ManifestList):
            image = target.select(platform)
            self.observer.append({"event": "select-platform", "ref": ref, "platform": platform})
        else:
            image = target

        new_layers = 0
        shared_layers = 0
        parent: str | None = None
        for layer in image.layers:
            if self.content.has(layer.digest):
                shared_layers += 1
            else:
                self.content.put(layer.digest, layer)
                new_layers += 1
            snap_name = f"{ref}:{layer.digest}"
            self.snapshotter.commit_layer(snap_name, layer, parent=parent)
            parent = snap_name

        self.observer.append({
            "event": "pull",
            "ref": ref,
            "platform": platform,
            "new_layers": new_layers,
            "shared_layers": shared_layers,
            "total_layers": len(image.layers),
        })
        return image

    # ---------- 容器：run = pull + prepare rootfs + create + start ----------
    def run(
        self,
        ref: str,
        name: str,
        platform: str = "linux/amd64",
        cpu_quota_us: int = -1,
        memory_max: int = -1,
        pids_max: int = -1,
        readonly_rootfs: bool = False,
    ) -> Container:
        """对应 `docker run`：拉镜像 → prepare rootfs → 生成 OCI config → create → start。"""
        image = self.pull(ref, platform=platform)
        top_snap = f"{ref}:{image.layers[-1].digest}"
        active_key = f"{name}:rootfs"
        self.snapshotter.prepare(active_key, parent=top_snap)

        config = OCIConfig(
            args=list(image.config.entrypoint) + list(image.config.cmd),
            env=list(image.config.env),
            user=image.config.user,
            cwd=image.config.working_dir,
            hostname=name,
            cpu_quota_us=cpu_quota_us,
            memory_max=memory_max,
            pids_max=pids_max,
            readonly_rootfs=readonly_rootfs,
            snapshot_key=active_key,
        )
        c = Container(name, config, self.snapshotter, observer=self.observer)
        c.create()
        c.start()
        self.containers[name] = c
        return c

    def status(self) -> list[dict]:
        return [
            {"name": c.id, "state": c.state, **c.cgroup.stat()}
            for c in self.containers.values()
        ]
