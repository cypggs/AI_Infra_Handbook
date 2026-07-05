"""CSI —— 容器存储接口的教学模拟。

对应真实组件：
  - ControllerServer ≈ CSI Controller Service（provisioner/attacher/external-snapshotter）
  - NodeServer ≈ CSI Node Service（kubelet 通过 csi.sock 调用）
  - VolumeStore ≈ CSI driver 内部状态 + etcd 中的 PV/VolumeAttachment
  - NodeVolumeStore ≈ 节点上 /var/lib/kubelet/plugins/kubernetes.io/csi/ 的 stage/publish 记录

模拟的关键语义：
  - CreateVolume 幂等
  - DeleteVolume 回收
  - RWO 单节点 attach，ROX 多节点只读 attach
  - NodeStage -> NodePublish 顺序，逆序卸载
  - VolumeAttachment 与 ControllerPublish/Unpublish 一致
  - snapshot 还原为新 volume
  - controller + node expand
"""
import copy


class CsiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class AlreadyExists(CsiError):
    def __init__(self, message):
        super().__init__(6, message)


class NotFound(CsiError):
    def __init__(self, message):
        super().__init__(5, message)


class InvalidArgument(CsiError):
    def __init__(self, message):
        super().__init__(3, message)


class FailedPrecondition(CsiError):
    def __init__(self, message):
        super().__init__(9, message)


# --------------------------------------------------------------------------- #
# 节点本地 stage/publish 记录
# --------------------------------------------------------------------------- #
class NodeVolumeStore:
    """每个 kubelet 一个实例：记录本节点上哪些 volume 已 stage / publish。"""

    def __init__(self, node_name):
        self.node_name = node_name
        # volume_id -> staging_path
        self._staged = {}
        # volume_id -> {pod_sandbox_id: target_path, read_only}
        self._published = {}

    def is_staged(self, volume_id):
        return volume_id in self._staged

    def stage(self, volume_id, staging_path):
        if volume_id in self._staged:
            return
        self._staged[volume_id] = staging_path

    def unstage(self, volume_id):
        if volume_id in self._published:
            raise FailedPrecondition(f"volume {volume_id} still published on {self.node_name}")
        self._staged.pop(volume_id, None)

    def publish(self, volume_id, sandbox_id, target_path, read_only=False):
        if volume_id not in self._staged:
            raise FailedPrecondition(f"volume {volume_id} must be staged before publish")
        self._published.setdefault(volume_id, {})[sandbox_id] = {
            "target_path": target_path,
            "read_only": read_only,
        }

    def unpublish(self, volume_id, sandbox_id):
        self._published.get(volume_id, {}).pop(sandbox_id, None)
        if volume_id in self._published and not self._published[volume_id]:
            del self._published[volume_id]

    def is_published_to_pod(self, volume_id, sandbox_id):
        return sandbox_id in self._published.get(volume_id, {})

    def published_pods(self, volume_id):
        return list(self._published.get(volume_id, {}).keys())


# --------------------------------------------------------------------------- #
# CSI Controller / Node Service
# --------------------------------------------------------------------------- #
class ControllerServer:
    """模拟 CSI Controller Service。"""

    def __init__(self, store):
        self.store = store

    def create_volume(self, name, *, size_gi, access_modes=None, source_snapshot=None):
        """CreateVolume：幂等，同名返回同一 volume。"""
        existing = self.store.get_volume_by_name(name)
        if existing is not None:
            return existing
        size = size_gi
        if source_snapshot:
            snap = self.store.get_snapshot(source_snapshot)
            if snap is None:
                raise NotFound(f"snapshot {source_snapshot} not found")
            size = max(size, snap["sizeGi"])
        vol = self.store.create_volume(name, size, access_modes or ["ReadWriteOnce"],
                                       source_snapshot=source_snapshot)
        return vol

    def delete_volume(self, volume_id):
        vol = self.store.get_volume(volume_id)
        if vol is None:
            return
        if self.store.is_attached(volume_id):
            raise FailedPrecondition(f"volume {volume_id} is still attached")
        self.store.delete_volume(volume_id)

    def controller_publish_volume(self, volume_id, node_name, *, read_only=False):
        """ControllerPublishVolume：RWO 只能 attach 到一个节点；ROX 可多节点只读。"""
        vol = self.store.get_volume(volume_id)
        if vol is None:
            raise NotFound(f"volume {volume_id} not found")
        attachments = self.store.attachments_for(volume_id)
        # RWO：已经 attach 到别的节点就拒绝
        if vol["spec"]["accessModes"] == ["ReadWriteOnce"]:
            for other in attachments:
                if other["spec"]["nodeName"] != node_name:
                    raise FailedPrecondition(
                        f"RWO volume {volume_id} already attached to {other['spec']['nodeName']}"
                    )
        # ROX：只允许 read_only attach
        if "ReadOnlyMany" in vol["spec"]["accessModes"] and not read_only:
            raise FailedPrecondition(f"ROX volume {volume_id} must be attached read-only")
        va = self.store.attach(volume_id, node_name, read_only=read_only)
        return va

    def controller_unpublish_volume(self, volume_id, node_name):
        self.store.detach(volume_id, node_name)

    def create_snapshot(self, volume_id, snapshot_name):
        vol = self.store.get_volume(volume_id)
        if vol is None:
            raise NotFound(f"volume {volume_id} not found")
        return self.store.create_snapshot(snapshot_name, volume_id, vol["spec"]["sizeGi"])

    def controller_expand_volume(self, volume_id, new_size_gi):
        vol = self.store.get_volume(volume_id)
        if vol is None:
            raise NotFound(f"volume {volume_id} not found")
        if new_size_gi < vol["spec"]["sizeGi"]:
            raise InvalidArgument("new size must be >= current size")
        # controller 侧扩展（云盘扩容）
        self.store.set_volume_spec(volume_id, {"sizeGi": new_size_gi})
        self.store.set_volume_status(volume_id, {"controller_expanded": True})
        return self.store.get_volume(volume_id)


class NodeServer:
    """模拟 CSI Node Service。"""

    def __init__(self, store, node_name, node_store):
        self.store = store
        self.node_name = node_name
        self.node_store = node_store

    def node_stage_volume(self, volume_id, staging_path):
        if self.store.get_volume(volume_id) is None:
            raise NotFound(f"volume {volume_id} not found")
        va = self.store.get_attachment(volume_id, self.node_name)
        if va is None:
            raise FailedPrecondition(f"volume {volume_id} not attached to {self.node_name}")
        self.node_store.stage(volume_id, staging_path)

    def node_publish_volume(self, volume_id, sandbox_id, target_path, read_only=False):
        va = self.store.get_attachment(volume_id, self.node_name)
        if va is None:
            raise FailedPrecondition(f"volume {volume_id} not attached to {self.node_name}")
        if va["spec"].get("readOnly"):
            read_only = True
        self.node_store.publish(volume_id, sandbox_id, target_path, read_only=read_only)

    def node_unpublish_volume(self, volume_id, sandbox_id):
        self.node_store.unpublish(volume_id, sandbox_id)

    def node_unstage_volume(self, volume_id):
        self.node_store.unstage(volume_id)

    def node_expand_volume(self, volume_id):
        vol = self.store.get_volume(volume_id)
        if vol is None:
            raise NotFound(f"volume {volume_id} not found")
        if not vol["status"].get("controller_expanded"):
            raise FailedPrecondition("controller expand must happen before node expand")
        self.store.set_volume_status(volume_id, {"controller_expanded": True, "node_expanded": True})
        return self.store.get_volume(volume_id)


# --------------------------------------------------------------------------- #
# VolumeStore：CSI 侧全局状态
# --------------------------------------------------------------------------- #
class VolumeStore:
    def __init__(self):
        # volume_id -> volume dict
        self._volumes = {}
        # snapshot_name -> snapshot dict
        self._snapshots = {}
        # (volume_id, node_name) -> VolumeAttachment
        self._attachments = {}
        self._counter = 0

    def _vid(self, name):
        return f"vol-{name}"

    def create_volume(self, name, size_gi, access_modes, source_snapshot=None):
        vid = self._vid(name)
        if vid in self._volumes:
            return copy.deepcopy(self._volumes[vid])
        self._counter += 1
        vol = {
            "volume_id": vid,
            "metadata": {"name": name},
            "spec": {
                "sizeGi": size_gi,
                "accessModes": list(access_modes),
            },
            "status": {
                "controller_expanded": False,
                "node_expanded": False,
            },
            "sourceSnapshot": source_snapshot,
            "attachments": {},
        }
        self._volumes[vid] = vol
        return copy.deepcopy(vol)

    def get_volume(self, volume_id):
        return copy.deepcopy(self._volumes.get(volume_id))

    def get_volume_by_name(self, name):
        return copy.deepcopy(self._volumes.get(self._vid(name)))

    def set_volume_status(self, volume_id, status):
        if volume_id in self._volumes:
            self._volumes[volume_id]["status"].update(status)

    def set_volume_spec(self, volume_id, spec):
        if volume_id in self._volumes:
            self._volumes[volume_id]["spec"].update(spec)

    def delete_volume(self, volume_id):
        self._volumes.pop(volume_id, None)

    def create_snapshot(self, name, volume_id, size_gi):
        if name in self._snapshots:
            return copy.deepcopy(self._snapshots[name])
        snap = {"name": name, "volume_id": volume_id, "sizeGi": size_gi}
        self._snapshots[name] = snap
        return copy.deepcopy(snap)

    def get_snapshot(self, name):
        return copy.deepcopy(self._snapshots.get(name))

    def attach(self, volume_id, node_name, read_only=False):
        k = (volume_id, node_name)
        if k in self._attachments:
            va = self._attachments[k]
            va["status"]["attached"] = True
            return copy.deepcopy(va)
        va = {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "VolumeAttachment",
            "metadata": {"name": f"va-{volume_id}-{node_name}"},
            "spec": {
                "nodeName": node_name,
                "attacher": "fake.csi",
                "source": {"persistentVolumeName": volume_id},
                "readOnly": read_only,
            },
            "status": {"attached": True},
        }
        self._attachments[k] = va
        vol = self._volumes[volume_id]
        vol["attachments"][node_name] = {"read_only": read_only}
        return copy.deepcopy(va)

    def detach(self, volume_id, node_name):
        k = (volume_id, node_name)
        self._attachments.pop(k, None)
        vol = self._volumes.get(volume_id)
        if vol:
            vol["attachments"].pop(node_name, None)

    def get_attachment(self, volume_id, node_name):
        return copy.deepcopy(self._attachments.get((volume_id, node_name)))

    def attachments_for(self, volume_id):
        return [copy.deepcopy(v) for k, v in self._attachments.items() if k[0] == volume_id]

    def is_attached(self, volume_id):
        return any(k[0] == volume_id for k in self._attachments)

    def is_attached_to(self, volume_id, node_name):
        return (volume_id, node_name) in self._attachments
