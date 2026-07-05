"""kubelet.py —— 节点代理的教学模拟。

核心职责：
  - watch 分配到本节点（nodeName==self）的 Pod
  - syncPod：
      1. CNI ADD（分配 sandbox_id、Pod IP、写入路由）
      2. CSI NodeStage / NodePublish（挂载 PVC 到容器）
      3. 更新 Pod status.podIP / status.phase
  - deletePod：
      1. CSI NodeUnpublish / NodeUnstage / ControllerUnpublish
      2. CNI DEL（回收 IP、删除 network attachment）
      3. 更新 Pod status

单线程、可步进；所有状态变更通过 FakeApiServer，status 更新带乐观锁重试。
"""
import copy

from . import csi, model
from .apiserver import Conflict


class Kubelet:
    """每个节点一个 Kubelet 实例。"""

    def __init__(self, node_name, apiserver, cni_plugin, csi_controller,
                 node_store, route_manager, clock, max_retries=3):
        self.node_name = node_name
        self.api = apiserver
        self.cni = cni_plugin
        self.csi_ctrl = csi_controller
        self.node_store = node_store
        self.csi_node = csi.NodeServer(csi_controller.store, node_name, node_store)
        self.routes = route_manager
        self.clock = clock
        self.max_retries = max_retries
        # pod key (namespace/name) -> sandbox_id
        self._sandbox = {}
        # pod key -> {vol_name: {published: bool, target_path}}
        self._volume_state = {}

    # ---------------- 内部工具 ---------------- #
    def _pod_key(self, pod):
        return (pod["metadata"]["namespace"], pod["metadata"]["name"])

    def _sandbox_id(self, pod):
        k = self._pod_key(pod)
        if k not in self._sandbox:
            self._sandbox[k] = f"sandbox-{self.node_name}-{pod['metadata']['name']}"
        return self._sandbox[k]

    def _node(self):
        n = self.api.get(model.NODE_KIND, "default", self.node_name)
        if n is None:
            raise RuntimeError(f"node {self.node_name} not found")
        return n

    def _update_status(self, pod, mutate_fn):
        """带乐观锁重试的 status 更新。"""
        for _ in range(self.max_retries):
            cur = self.api.get(model.POD_KIND, pod["metadata"]["namespace"],
                               pod["metadata"]["name"])
            if cur is None:
                return None
            updated = copy.deepcopy(cur)
            mutate_fn(updated)
            try:
                return self.api.update_status(updated)
            except Conflict:
                continue
        raise Conflict(f"failed to update status after {self.max_retries} retries")

    # ---------------- Pod 网络 ---------------- #
    def _ensure_network(self, pod):
        sandbox_id = self._sandbox_id(pod)
        node = self._node()
        if pod["status"].get("podIP"):
            return
        result = self.cni.add(pod, sandbox_id, node)
        pod_ip = result.get("podIP")

        def set_ip(p):
            p["status"]["podIP"] = pod_ip
            p["status"]["phase"] = "Running"
            p["status"].setdefault("conditions", []).append({"type": "Ready", "status": "True"})

        self._update_status(pod, set_ip)
        # 在 apiserver 里记录 network attachment（模拟 CNI 把结果写回）
        try:
            self.api.create(model.make_network_attachment(
                pod["metadata"]["name"], pod["metadata"]["namespace"],
                node_name=self.node_name,
                pod_ip=pod_ip,
                sandbox_id=sandbox_id,
                routes=result.get("routes", []),
            ))
        except Exception:
            pass  # 已存在则忽略

    def _teardown_network(self, pod):
        sandbox_id = self._sandbox_id(pod)
        node = self._node()
        self.cni.del_(pod, sandbox_id, node)
        self._sandbox.pop(self._pod_key(pod), None)
        # 删除 network attachment
        try:
            self.api.delete(model.NETWORK_ATTACHMENT_KIND, pod["metadata"]["namespace"],
                            f"{pod['metadata']['name']}-{sandbox_id}")
        except Exception:
            pass

    # ---------------- Pod 存储 ---------------- #
    def _ensure_volumes(self, pod):
        vol_mounts = model.pod_volumes(pod)
        if not vol_mounts:
            return
        state = self._volume_state.setdefault(self._pod_key(pod), {})
        for vol_name, claim_name in vol_mounts.items():
            self._ensure_pvc_bound(claim_name)
            pv = self._pv_for_claim(claim_name)
            if pv is None:
                continue
            vol_id = pv["spec"]["csi"]["volumeHandle"]
            target = f"/var/lib/kubelet/pods/{pod['metadata']['name']}/volumes/{vol_name}"
            staging = f"/var/lib/kubelet/plugins/kubernetes.io/csi/{vol_id}"

            # ControllerPublish
            if not self.csi_ctrl.store.is_attached_to(vol_id, self.node_name):
                read_only = model.is_rox(pv) or self._read_only_mount(pod, vol_name)
                self.csi_ctrl.controller_publish_volume(vol_id, self.node_name, read_only=read_only)

            # NodeStage
            if not self.node_store.is_staged(vol_id):
                self.csi_node.node_stage_volume(vol_id, staging)

            # NodePublish
            sandbox_id = self._sandbox_id(pod)
            if not self.node_store.is_published_to_pod(vol_id, sandbox_id):
                read_only = model.is_rox(pv) or self._read_only_mount(pod, vol_name)
                self.csi_node.node_publish_volume(vol_id, sandbox_id, target, read_only=read_only)

            state[vol_name] = {"published": True, "target_path": target}

    def _read_only_mount(self, pod, vol_name):
        for vol in pod["spec"].get("volumes", []):
            if vol["name"] == vol_name:
                pvc = vol.get("persistentVolumeClaim", {})
                return pvc.get("readOnly", False)
        return False

    def _ensure_pvc_bound(self, claim_name):
        pvc = self.api.get(model.PVC_KIND, "default", claim_name)
        if pvc is None:
            return
        if pvc["status"].get("phase") == "Bound" and pvc["status"].get("bound_pv"):
            return
        # 由 kubelet / 外部 provisioner 触发：找可用 PV 或调用 CSI CreateVolume
        pv_name = f"pv-{claim_name}"
        pv = self.api.get(model.PV_KIND, "", pv_name)
        if pv is None:
            # 动态 provision
            vol = self.csi_ctrl.create_volume(
                claim_name, size_gi=self._parse_size(pvc["spec"]["resources"]["requests"]["storage"]),
                access_modes=pvc["spec"].get("accessModes", ["ReadWriteOnce"]))
            pv = model.make_pv(pv_name, capacity_gi=vol["spec"]["sizeGi"],
                               access_modes=vol["spec"]["accessModes"],
                               volume_handle=vol["volume_id"])
            self.api.create(pv)
        # 绑定
        if pv["spec"]["claimRef"] is None:
            pv["spec"]["claimRef"] = {"namespace": "default", "name": claim_name}
            pv["status"]["phase"] = "Bound"
            self.api.update(pv)
        if pvc["status"].get("bound_pv") != pv_name:
            pvc["status"]["phase"] = "Bound"
            pvc["status"]["bound_pv"] = pv_name
            self.api.update_status(pvc)

    def _parse_size(self, s):
        if isinstance(s, int):
            return s
        if s.endswith("Gi"):
            return int(s[:-2])
        if s.endswith("G"):
            return int(s[:-1])
        return int(s)

    def _pv_for_claim(self, claim_name):
        pvc = self.api.get(model.PVC_KIND, "default", claim_name)
        if pvc is None:
            return None
        pv_name = pvc["status"].get("bound_pv")
        if not pv_name:
            return None
        return self.api.get(model.PV_KIND, "", pv_name)

    def _teardown_volumes(self, pod):
        vol_mounts = model.pod_volumes(pod)
        sandbox_id = self._sandbox_id(pod)
        for vol_name, claim_name in reversed(list(vol_mounts.items())):
            pv = self._pv_for_claim(claim_name)
            if pv is None:
                continue
            vol_id = pv["spec"]["csi"]["volumeHandle"]
            # NodeUnpublish
            if self.node_store.is_published_to_pod(vol_id, sandbox_id):
                self.csi_node.node_unpublish_volume(vol_id, sandbox_id)
            # NodeUnstage
            if self.node_store.is_staged(vol_id) and not self.node_store.published_pods(vol_id):
                self.csi_node.node_unstage_volume(vol_id)
            # ControllerUnpublish
            if self.csi_ctrl.store.is_attached_to(vol_id, self.node_name):
                self.csi_ctrl.controller_unpublish_volume(vol_id, self.node_name)
        self._volume_state.pop(self._pod_key(pod), None)

    # ---------------- 对外 API ---------------- #
    def sync_pod(self, pod):
        """幂等收敛：网络 + 存储 + 状态。"""
        if pod["status"].get("phase") in ("Succeeded", "Failed", "Terminating"):
            return
        self._ensure_network(pod)
        self._ensure_volumes(pod)

    def delete_pod(self, pod):
        """清理 Pod 的网络与存储。"""
        self._teardown_volumes(pod)
        self._teardown_network(pod)

        def set_terminated(p):
            p["status"]["phase"] = "Succeeded"
            p["status"]["podIP"] = ""

        try:
            self._update_status(pod, set_terminated)
        except Exception:
            pass
