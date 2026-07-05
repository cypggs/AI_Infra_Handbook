"""Kubelet —— 模拟 kubelet 的 device-manager 部分。

对应真实组件：
  - `sync_pod` 对应 kubelet 在 Pod 被调度到本节点后调用的设备分配流程
  - `delete_pod` 对应 kubelet 在 Pod 删除时回收设备
  - 通过 device plugin 的 `Allocate` 获取环境变量并注入 `NVIDIA_VISIBLE_DEVICES`
"""
from . import model
from .device_plugin import DevicePlugin, DevicePluginError


class KubeletError(Exception):
    pass


class Kubelet:
    def __init__(self, api, node_name):
        self.api = api
        self.node_name = node_name
        self._plugins = {}                      # resource_name -> DevicePlugin
        self._pod_allocations = {}              # pod_key -> {container_name: [indices]}

    # ---------------- 插件管理 ---------------- #
    def register_plugin(self, plugin):
        if not isinstance(plugin, DevicePlugin):
            raise KubeletError("plugin must be a DevicePlugin instance")
        self._plugins[plugin.resource_name] = plugin

    def plugins(self):
        return dict(self._plugins)

    # ---------------- Pod 生命周期 ---------------- #
    def sync_pod(self, pod):
        """同步 Pod：为每个需要设备的容器调用对应 DevicePlugin.Allocate。"""
        pod_key = model.key(pod)
        node_name = pod["spec"].get("nodeName")
        if node_name and node_name != self.node_name:
            raise KubeletError(f"pod bound to {node_name}, not this kubelet {self.node_name}")

        allocations = {}
        for container in pod["spec"].get("containers", []):
            res = container.get("resources") or {}
            requests = res.get("requests") or {}
            for resource_name, amount in requests.items():
                amount = int(amount)
                if amount == 0:
                    continue
                plugin = self._plugins.get(resource_name)
                if plugin is None:
                    # 未知扩展资源：跳过（真实 kubelet 会拒绝）
                    continue

                available = plugin.available_indices()
                if len(available) < amount:
                    raise KubeletError(
                        f"not enough {resource_name} on {self.node_name}: "
                        f"want {amount}, available {len(available)}"
                    )
                chosen = available[:amount]
                response = plugin.allocate(chosen)
                allocations.setdefault(container["name"], []).extend(chosen)

                # 把 NVIDIA_VISIBLE_DEVICES 注入容器环境变量
                envs = response.get("envs") or {}
                container.setdefault("env", [])
                for k, v in envs.items():
                    # 去重更新
                    container["env"] = [e for e in container["env"] if e.get("name") != k]
                    container["env"].append({"name": k, "value": v})

        self._pod_allocations[pod_key] = allocations
        pod["status"]["phase"] = "Running"
        pod["status"]["allocated_devices"] = allocations
        return allocations

    def delete_pod(self, pod):
        """删除 Pod：释放该 Pod 占用的所有设备。"""
        pod_key = model.key(pod)
        allocations = self._pod_allocations.pop(pod_key, {})
        all_indices = []
        for resource_name, plugin in self._plugins.items():
            for indices in allocations.values():
                # MIG plugin和整卡插件的 resource_name 不同，release 会忽略不属于该插件的 id
                plugin.release(indices)
                all_indices.extend(indices)

        # 同时更新 pod 对象本身状态
        pod["spec"]["nodeName"] = ""
        pod["status"]["phase"] = "Succeeded"
        pod["status"]["allocated_devices"] = {}
        return all_indices

    def pod_allocations(self):
        """返回当前 kubelet 上所有 Pod 的设备占用。"""
        return {k: dict(v) for k, v in self._pod_allocations.items()}

    def allocated_count(self, resource_name=None):
        if resource_name:
            plugin = self._plugins.get(resource_name)
            return plugin.allocated_count() if plugin else 0
        return sum(p.allocated_count() for p in self._plugins.values())
