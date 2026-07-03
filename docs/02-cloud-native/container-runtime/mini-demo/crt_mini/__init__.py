"""crt_mini — 容器运行时概念模拟器（Container Runtime mini-demo）。

一个纯 Python、确定性、零依赖的"容器运行时概念模拟器"，在 macOS/CPU 上即可运行。
它**不**调用任何真实 Linux 系统调用（unshare/clone/cgroup），而是用 Python 数据结构
模拟容器运行时的核心概念：镜像分层与内容寻址、overlayfs 联合挂载与 copy-on-write、
namespace 隔离视图、cgroup 资源限制与计量（含 CPU throttle / 内存 OOM）、
OCI Runtime 的 create/start 生命周期、高层运行时（mini-containerd）的 pull→run 链、
多架构 manifest list。

详见 docs/02-cloud-native/container-runtime/07-mini-demo.md。
"""

__version__ = "0.1.0"
