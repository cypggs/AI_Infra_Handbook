"""gpu_scheduling_mini —— 用纯标准库从零实现的 Kubernetes GPU 调度教学模拟器。

把 kubelet / Device Plugin / kube-scheduler / Volcano / GPU Topology 的核心机制
在一个进程里重建出来，对应关系：

    本模块                 真实组件
    ─────────────────────────────────────────────────────────────
    clock.py              系统 wall-clock（FakeClock 让步进可复现）
    apiserver.py          kube-apiserver + etcd（rv、乐观锁、generation、/status、watch）
    model.py              K8s 资源模型（Node / Pod / PodGroup / Queue / GPU / Resources）
    device_plugin.py      NVIDIA Device Plugin（注册、ListAndWatch、Allocate、health check）
    kubelet.py            kubelet device-manager（sync_pod → Allocate，delete_pod → release）
    scheduler.py          kube-scheduler + Scheduler Framework（Filter / Score / Reserve / Bind）
    topology.py           GPU 拓扑感知调度（NUMA / PCIe / NVSwitch 亲和性打分）
    gang.py               Volcano / Coscheduling（PodGroup all-or-nothing）
    demo.py               端到端场景演示

整个系统是单线程、可步进的确定性模拟：用 FakeClock 替代真实时间，于是
"t=0 device plugin 注册 → t=1 ListAndWatch → t=2 Allocate" 的时间线可以精确复现。
"""

from .clock import Clock, FakeClock, RealClock
from .apiserver import FakeApiServer, ApiError, Conflict, NotFound
from . import model
from .device_plugin import DevicePlugin
from .kubelet import Kubelet
from .scheduler import Scheduler
from .topology import Topology, TopologyScorer
from .gang import GangScheduler, PodGroupState

__all__ = [
    "Clock",
    "FakeClock",
    "RealClock",
    "FakeApiServer",
    "ApiError",
    "Conflict",
    "NotFound",
    "model",
    "DevicePlugin",
    "Kubelet",
    "Scheduler",
    "Topology",
    "TopologyScorer",
    "GangScheduler",
    "PodGroupState",
]
