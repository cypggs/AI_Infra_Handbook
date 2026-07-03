"""helm_mini — 一个纯 Python 的“微型 Helm”教学模拟器。

它**不**连接真实 Kubernetes 集群，而是在内存里模拟 Helm 的核心机制：
Chart 结构 → values 深合并 → Go template 渲染 → Release 生命周期
(install/upgrade/rollback/uninstall) → 三方合并 Patch → Release 存储（Secret）。

设计目标：让你**读着代码**就能理解 Helm 的设计动机与运行机制，
而不是去理解 K8s API 细节。详见 README.md 与 07-mini-demo.md。
"""

from .chart import Chart, ChartMetadata
from .values import merge_values
from .template import Engine, render_text
from .engine import render_chart, ReleaseContext
from .release import Release, ReleaseStatus
from .storage import Storage, SecretDriver
from .kube import KubeClient, three_way_merge
from .action import Configuration, Install, Upgrade, Rollback, Uninstall

__all__ = [
    "Chart",
    "ChartMetadata",
    "merge_values",
    "Engine",
    "render_text",
    "render_chart",
    "ReleaseContext",
    "Release",
    "ReleaseStatus",
    "Storage",
    "SecretDriver",
    "KubeClient",
    "three_way_merge",
    "Configuration",
    "Install",
    "Upgrade",
    "Rollback",
    "Uninstall",
]
