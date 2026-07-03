"""k8s_mini — 一个纯 Python、单线程、tick 驱动的微型 Kubernetes 模拟器。

教学目标：在不依赖真实集群的前提下，忠实演示 Kubernetes 的核心机制——
声明式 API + 控制循环、调度框架（Filter/Score/Reserve/Bind、调度周期 vs 绑定周期、
Gang 调度）、Device Plugin + GPU 调度、Deployment 滚动升级与自愈。
"""

from k8s_mini.model import (  # noqa: F401
    Resources,
    Taint,
    Node,
    Container,
    Pod,
    PodPhase,
    Deployment,
    ReplicaSet,
    PriorityClass,
)
from k8s_mini.store import Store, Event, EventType  # noqa: F401
from k8s_mini.apiserver import ApiServer, AdmissionError  # noqa: F401
from k8s_mini.device_plugin import GpuDevicePlugin  # noqa: F401
from k8s_mini.scheduler import Scheduler  # noqa: F401
from k8s_mini.kubelet import Kubelet  # noqa: F401
from k8s_mini.controller import DeploymentController, ReplicaSetController  # noqa: F401
from k8s_mini.observer import Observer  # noqa: F401

__version__ = "0.1.0"
