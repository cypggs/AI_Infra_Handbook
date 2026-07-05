"""cni_csi_mini —— 用纯标准库从零实现的 Kubernetes CNI/CSI 教学模拟器。

把容器网络与存储插件的核心机制在一个 Python 进程里重建出来，对应关系：

    本模块            真实 K8s / CSI / CNI 组件
    ────────────────  ─────────────────────────────────────────
    model.py          Pod / Node / PVC / PV / Volume / VolumeAttachment 资源模型
    apiserver.py      kube-apiserver + etcd（乐观并发、resourceVersion、watch 事件流）
    cni.py            CNI 插件接口、bridge、IPAM、路由表、NetworkPolicy
    csi.py            CSI Controller / Node Service、VolumeStore、NodeVolumeStore
    kubelet.py        kubelet（CNI ADD/DEL + CSI stage/publish/unpublish/unstage）
    demo.py           六个端到端场景演示

整个系统是单线程、可步进的确定性模拟：用 FakeClock 替代真实时间，于是第 7 章描述的
"Pod 创建 → CNI ADD 分配 IP → CSI stage/publish 挂载 → 删除时逆序卸载" 的时间线可以
精确复现。
"""

from cni_csi_mini.clock import Clock, RealClock, FakeClock  # noqa: F401
from cni_csi_mini.model import (  # noqa: F401
    POD_KIND, NODE_KIND, PVC_KIND, PV_KIND,
    VOLUME_ATTACHMENT_KIND, NETWORK_ATTACHMENT_KIND, VOLUME_KIND,
    make_node, make_pod, make_pvc, make_pv, make_volume,
    make_volume_attachment, make_network_attachment,
    volume_mount, container_mount,
    key, deep_copy, pod_volumes, is_rwo, is_rox,
)
from cni_csi_mini.apiserver import FakeApiServer, ApiError, Conflict, NotFound  # noqa: F401
from cni_csi_mini.cni import (  # noqa: F401
    IPAM, BridgePlugin, PluginChain, RouteManager, NetworkPolicyManager,
    make_network_policy, allow_all_ingress, allow_all_egress,
    default_deny_ingress, default_deny_egress, pod_selector,
)
from cni_csi_mini.csi import (  # noqa: F401
    VolumeStore, NodeVolumeStore, ControllerServer, NodeServer,
    CsiError, AlreadyExists, NotFound as CsiNotFound,
    InvalidArgument, FailedPrecondition,
)
from cni_csi_mini.kubelet import Kubelet  # noqa: F401

__version__ = "0.1.0"
