# 容器运行时概念模拟器（crt_mini）

一个**纯 Python、确定性、零依赖**的"容器运行时概念模拟器"，在 macOS/CPU 上即可运行。
它**不**调用任何真实 Linux 系统调用（`unshare`/`clone`/cgroup），而是用 Python 数据结构
忠实模拟容器运行时的核心概念，让你用 0.05 秒看清真实运行时要花几小时才能观察到的东西。

> 配套文档：`docs/02-cloud-native/container-runtime/07-mini-demo.md`
> **诚实声明**：这是一个**概念模拟器**，不启动任何真实容器。它教的是"机制与设计权衡"，
> 不是"真实内核行为"。要在真实容器上验证这些概念，请用 Docker/`crictl` 复现。

## 模拟了什么

| 概念 | 模块 | 对应真实运行时 |
|---|---|---|
| 镜像分层 + 内容寻址 | `image.py` | OCI image-spec（Layer/config/manifest） |
| Content Store（按 digest 去重） | `content.py` | containerd Content Store |
| overlayfs 联合挂载 + copy-on-write | `snapshot.py` | containerd overlayfs snapshotter |
| namespace 隔离视图 | `namespace.py` | Linux namespaces（pid/net/mnt/uts/ipc/user） |
| cgroup 限制 + CPU throttle + OOM | `cgroup.py` | Linux cgroup v2（cpu.max/memory.max/pids.max） |
| OCI create/start/exec 生命周期 | `runtime.py` | runc/libcontainer |
| 高层运行时 pull→run 全链路 | `engine.py` | containerd（mini-containerd） |
| 镜像仓库 + 多架构 manifest list | `registry.py` | OCI registry + image index |

## 运行

```bash
# 6 个场景演示（推荐先看）
python3 -m crt_mini.demo

# 或安装后
pip install -e ".[dev]"
crt-mini-demo
```

## 测试

```bash
pip install -e ".[dev]"
pytest tests/ -q
# 40 passed in 0.05s
```

测试把每个机制的关键不变量固化为契约（COW 整文件复制、CPU throttle、OOM 停容器、
manifest list 平台选择、pull 去重……），改代码时 `pytest` 会立刻告诉你有没有破坏。

## 6 个演示场景

1. **镜像分层与内容寻址去重**：pull 一个镜像，看 manifest 列出各层 digest；重复 pull
   同一镜像，Content Store 命中去重（`new=0 shared=2`）。
2. **overlayfs 联合挂载 + COW 代价**：看 union 视图合并了下层文件；写新文件不触发 COW；
   **改一个已有文件哪怕 1 字节，整个文件被 copy-up**（演示 overlayfs 关键代价）。
3. **namespace 隔离**：两个容器各有独立的 6 种 namespace，只看到自己的成员；
   `shared_with` 演示 Pod 内容器共享 net（pause 容器语义）。
4. **cgroup 限制**：`cpu.max=50000 100000`（0.5 核）每周期用 80000us → `nr_throttled` 累计；
   `memory.max=4096` 分配超限 → `oom`，容器状态变 `stopped`、exit_code=137。
5. **OCI 生命周期**：手动走 `create`（state=created，rootfs 就绪但进程未 exec）→ `start`
   （running，PID 1）→ `exec`（setns 进容器起 PID 2）→ `stop`，对应 runc 命令。
6. **多架构 manifest list**：`myreg/ai-server:v1` 支持 amd64/arm64，按 `--platform` 选择
   对应子镜像（base 层内容随架构不同）。

## 与真实运行时的本质差异（诚实的边界）

| 维度 | 模拟器 | 真实运行时 |
|---|---|---|
| 隔离机制 | Python 对象（Namespace 数据类） | 真实 `clone(CLONE_NEW*)` 系统调用 |
| 资源限制 | 数据结构累加/比较 | 真实 cgroupfs（内核强制节流/OOM） |
| 文件系统 | Python dict 模拟 union | 真实 overlayfs 内核挂载 |
| 进程 | 模拟的 PID 计数器 | 真实 `fork/exec`，PID 1 |
| 网络 | 完全不模拟 | CNI 真实组网、iptables/路由 |
| 镜像 | 内存中的示例数据 | 真实 registry、压缩层、digest 校验 |

**结论**：模拟器是理解运行时**机制与设计权衡**的最佳工具，但不能替代真实运行时的操作经验。
学完本模拟器后，建议在装了 Docker 的机器上用 `dive` 拆一个真实镜像、用 `crictl` 看一次容器
创建，对照模拟器的输出，你会对两者都有更深的理解。

## 目录结构

```
crt_mini/
├── __init__.py
├── image.py        # Layer / ImageConfig / Image / ManifestList
├── content.py      # ContentStore（按 digest 去重）
├── snapshot.py     # Snapshotter（union + COW）
├── namespace.py    # NamespaceSet（隔离 + Pod 共享）
├── cgroup.py       # Cgroup（cpu/memory/pids + throttle/OOM）
├── runtime.py      # Container（OCI create/start/exec）
├── registry.py     # Registry（示例镜像 + 多架构）
├── engine.py       # HighLevelRuntime（pull/run）
└── demo.py         # run_demo()：6 场景入口
tests/              # 40 个 pytest 用例
pyproject.toml
conftest.py
```
