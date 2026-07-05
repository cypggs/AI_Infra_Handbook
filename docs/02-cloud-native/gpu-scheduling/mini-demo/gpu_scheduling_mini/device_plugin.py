"""DevicePlugin —— 模拟 NVIDIA Device Plugin。

对应真实组件：
  - `Registration` 对应 device plugin 向 kubelet 的插件注册服务注册
  - `ListAndWatch` 返回设备列表与健康状态
  - `Allocate` 在 Pod 绑定到节点后被 kubelet 调用，返回环境变量、挂载、设备 ID
  - `PreStartContainer` 在容器启动前调用
  - `health check` 模拟设备故障与恢复
  - `release` 在 Pod 删除时由 kubelet 调用，回收设备

本模拟器不实现 gRPC，所有调用都是同步方法调用。
"""
from . import model


class DevicePluginError(Exception):
    pass


class DevicePlugin:
    """模拟一个 K8s Device Plugin（以 nvidia.com/gpu 为例）。"""

    def __init__(self, resource_name, devices, clock=None):
        """
        resource_name: 例如 "nvidia.com/gpu"
        devices: list[GPU]
        clock: 可选 FakeClock，用于时间戳
        """
        self.resource_name = resource_name
        self.devices = {d.index: d for d in devices}
        self.registered = False
        self._clock = clock
        self._allocated = set()          # 已分配的设备索引
        self._allocations = {}           # pod_uid -> {container_name: [indices]}
        self._callbacks = []             # health 变化回调

    # ---------------- 注册 ---------------- #
    def register(self, kubelet):
        """向 kubelet 注册。真实场景通过 /var/lib/kubelet/device-plugins/kubelet.sock。"""
        kubelet.register_plugin(self)
        self.registered = True

    # ---------------- ListAndWatch ---------------- #
    def list_and_watch(self):
        """返回当前设备列表（真实 gRPC 流式返回）。"""
        return [
            {"id": str(d.index), "uuid": d.uuid, "health": d.health}
            for d in self.devices.values()
        ]

    # ---------------- Allocate ---------------- #
    def allocate(self, device_ids):
        """分配一组设备，返回 AllocateResponse（envs / mounts / devices）。

        device_ids: list[int] 或 list[str]，表示设备索引
        """
        indices = [int(x) for x in device_ids]
        if len(set(indices)) != len(indices):
            raise DevicePluginError("duplicate device ids in allocate request")

        for idx in indices:
            dev = self.devices.get(idx)
            if dev is None:
                raise DevicePluginError(f"device {idx} not found")
            if dev.health != "Healthy":
                raise DevicePluginError(f"device {idx} is unhealthy")
            if idx in self._allocated:
                raise DevicePluginError(f"device {idx} already allocated")

        for idx in indices:
            self._allocated.add(idx)

        # 环境变量 NVIDIA_VISIBLE_DEVICES 使用设备 UUID 或索引
        ids_str = ",".join(str(self.devices[idx].uuid) for idx in indices)
        response = {
            "envs": {"NVIDIA_VISIBLE_DEVICES": ids_str},
            "mounts": [],
            "devices": [
                {"id": str(idx), "uuid": self.devices[idx].uuid}
                for idx in indices
            ],
        }
        return response

    # ---------------- PreStartContainer ---------------- #
    def pre_start_container(self, device_ids):
        """容器启动前钩子，返回环境变量（真实场景还会做 CUDA 可见性设置等）。"""
        indices = [int(x) for x in device_ids]
        return {
            "envs": {
                "NVIDIA_VISIBLE_DEVICES": ",".join(str(self.devices[idx].uuid) for idx in indices)
            }
        }

    # ---------------- health check ---------------- #
    def on_health_change(self, callback):
        """注册健康状态变化回调。"""
        self._callbacks.append(callback)

    def health_check(self, device_id, healthy):
        """模拟设备健康检查。"""
        idx = int(device_id)
        dev = self.devices.get(idx)
        if dev is None:
            raise DevicePluginError(f"device {idx} not found")
        old = dev.health
        dev.health = "Healthy" if healthy else "Unhealthy"
        if old != dev.health:
            for cb in self._callbacks:
                cb(self.resource_name, idx, dev.health)
        return dev.health

    # ---------------- release ---------------- #
    def release(self, device_ids):
        """释放设备。"""
        for idx in (int(x) for x in device_ids):
            self._allocated.discard(idx)
            dev = self.devices.get(idx)
            if dev:
                dev.allocated = False

    # ---------------- 辅助 ---------------- #
    def allocated_count(self):
        return len(self._allocated)

    def healthy_count(self):
        return sum(1 for d in self.devices.values() if d.health == "Healthy")

    def healthy_indices(self):
        return [d.index for d in self.devices.values() if d.health == "Healthy"]

    def available_indices(self):
        """健康且未被分配的设备索引。"""
        return [
            d.index for d in self.devices.values()
            if d.health == "Healthy" and d.index not in self._allocated
        ]
