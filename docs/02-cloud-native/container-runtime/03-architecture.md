# 3. 架构设计：从 Docker CLI 到内核的分层栈

> 一句话理解：现代容器运行时是**严格分层的**——用户接口（docker/nerdctl/crictl）在最上层，下面是高层运行时（containerd，管镜像与生命周期），再下面是 containerd-shim（隔离容器与守护进程），最底层是低层运行时（runc，真正 fork/exec 容器进程）；而镜像的构建（BuildKit）与分发（registry）作为两个独立子系统旁挂在主链路上。本章画出这条完整的架构，并解释每层为何存在。

## 3.1 整体分层：一条从命令到内核的调用链

一条 `docker run`（或 `nerdctl run` / `crictl runp`）最终落到内核，要穿过这样的层次：

```
        docker / nerdctl / crictl            ← 用户接口层（CLI，可选）
                  │ gRPC / HTTP
                  ▼
        ┌─────────────────────┐
        │ Docker Engine        │            ← 可选层：构建/网络/卷/REST API
        │ (dockerd)            │               （K8s 节点上通常没有这一层）
        └─────────┬───────────┘
                  │ containerd API (gRPC)
                  ▼
        ┌─────────────────────┐
        │ containerd           │            ← 高层运行时（核心）
        │  ├ Image Service     │               镜像管理
        │  ├ Containers Service│               容器生命周期
        │  ├ Content Store     │               层内容存储
        │  ├ Snapshotter       │               overlayfs 快照
        │  ├ CRI plugin        │               对接 K8s kubelet
        │  └ Transfer Service  │               流式镜像传输
        └─────────┬───────────┘
                  │ OCI Runtime Spec
                  ▼
        ┌─────────────────────┐
        │ containerd-shim      │            ← 容器父进程（每容器一个）
        │ (containerd-shim-    │               解耦守护进程与容器
        │   runc-v2)           │
        └─────────┬───────────┘
                  │ exec runc
                  ▼
        ┌─────────────────────┐
        │ runc (libcontainer)  │            ← 低层运行时
        └─────────┬───────────┘               namespace/cgroup/mount/exec
                  │ clone/setns/cgroup syscalls
                  ▼
              Linux Kernel
```

旁挂的两个子系统：

- **BuildKit**（构建侧）：把 Dockerfile → OCI 镜像，旁挂在主链路（`docker build` / `nerdctl build` / `buildctl` 调用它）。
- **Registry**（分发侧）：OCI Distribution Spec 的镜像仓库，主链路通过它 `pull/push`。

下面自上而下逐层拆解。

## 3.2 用户接口层：CLI 是可选的"皮肤"

最上面的 CLI（`docker`、`nerdctl`、`crictl`、`podman`）只是**调用下层 API 的客户端**，本身不做运行时工作：

| CLI | 调用谁 | 典型场景 |
|---|---|---|
| `docker` | → dockerd → containerd | 开发者本地、CI 构建镜像 |
| `nerdctl` | → containerd（直接） | K8s 节点上调试（节点没 dockerd），Docker 兼容体验 |
| `crictl` | → CRI 接口（containerd/CRI-O） | K8s 节点调试，纯 CRI 命令 |
| `ctr` | → containerd 原生 API | containerd 底层调试（不友好，但最全） |
| `podman` | → 直接调 runc/conmon（无 daemon） | Red Hat 生态，daemonless、rootless |

> **关键认知**：K8s 节点上经常**只有 containerd**（没有 dockerd）。所以在节点上调试容器，你要用 `crictl` 或 `nerdctl`，而不是 `docker`。`docker` 命令不可用是 K8s 节点的常态（自 dockershim 移除后）。

## 3.3 Docker Engine（dockerd）：可选的"中间胖层"

`dockerd`（Docker Engine）是一个**可选层**——它提供：

- Dockerfile 构建（通过 BuildKit）、
- 网络管理（bridge/overlay/macvlan）、
- 卷（volume）管理、
- Docker Compose 协调、
- REST API（`/var/run/docker.sock`）、
- 把上面这些封装成 `docker` 命令体验。

在**K8s 节点上**，dockerd 通常不存在——K8s 直接通过 CRI 调 containerd，跳过 dockerd。dockerd 主要服务于**开发机与 CI**（构建镜像、本地运行）。

> 注意区分三个名字：**Docker（公司/产品）**、**Docker Engine = dockerd（守护进程）**、**Moby（moby/moby，dockerd 的开源上游）**。K8s 移除的是 dockershim（对接 dockerd 的适配层），不是禁止用 Docker 构建镜像。

## 3.4 containerd：高层运行时核心

**containerd** 是整个架构的"心脏"——一个精简、可嵌入、可扩展的高层运行时。它的内部架构（[官方 ARCHITECTURE.md](https://github.com/containerd/containerd/blob/main/docs/ARCHITECTURE.md)）分为多个解耦的子系统：

```
                     containerd daemon (单个 gRPC server)
   ┌───────────────────────────────────────────────────────────┐
   │   Metadata Store            Content Store (blobs, 按 digest)│
   │   (images / containers /    ──────────────────────────────│
   │    snapshots / leases)      Snapshotter (overlayfs 默认)    │
   │                                                             │
   │   ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐  │
   │   │ Runtime  │ │ Image    │ │ Transfer  │ │  CRI plug  │  │
   │   │ Service  │ │ Service  │ │ Service   │ │  (K8s)     │  │
   │   └────┬─────┘ └────┬─────┘ └───────────┘ └────────────┘  │
   │        │            │            ▲                          │
   │        ▼            ▼            │ pull/push               │
   │   ┌────────────────────────┐    │                          │
   │   │   containerd-shim (每容器一个)│◄───┘                    │
   │   └──────────┬─────────────┘                                │
   └──────────────┼─────────────────────────────────────────────┘
                  ▼
                runc (OCI runtime)
```

### 核心子系统职责

| 子系统 | 职责 |
|---|---|
| **Image Service** | 镜像的 CRUD、引用解析（tag/digest）、manifest 解析 |
| **Containers Service** | 容器对象的元数据、生命周期（create/start/stop/delete） |
| **Content Store** | 存镜像层的内容（blob），按 digest 寻址、去重 |
| **Snapshotter** | 把只读层解包成快照树，提供 rootfs 的"父-子"快照关系；overlayfs 是默认，也可换 btrfs/zfs/native/stargz/nydus |
| **Runtime Service** | 调用 OCI runtime（runc）+ shim 创建容器 |
| **CRI plugin** | 实现 K8s CRI gRPC 接口，内置在 containerd 进程内 |
| **Transfer Service** | 流式镜像 pull/push（containerd 2.x GA），支持 streaming + 惰性拉取 |
| **NRI**（Node Resource Interface） | 运行时插件接口，让 Device Plugin/扩展介入容器创建 |

### 为什么 containerd 这么"碎"

因为 containerd 的设计目标是**可嵌入、可按需取用**：

- 你可以只用它的 image pull（如某些构建工具），不用 runtime；
- 你可以换掉 snapshotter（用 stargz 做惰性拉取，或 nydus 做按需下载）；
- 你可以不加载 CRI plugin（非 K8s 场景）。

这种"乐高"式的可组合性，是它从 dockerd 那个"胖单体"里剥离出来后获得的核心价值。

## 3.5 containerd-shim：守护进程与容器解耦的关键

这是整个架构里**最巧妙**的一环，值得单独一节。

### 问题：为什么需要 shim？

早期 Docker 的容器进程**直接由 dockerd fork 出来**，导致一个问题：**dockerd 重启会杀掉所有容器**（因为容器进程的父进程是 dockerd，父进程死了孤儿进程会被重新托管但容器管理状态丢失）。

更糟：runc 是一个**短命工具**——它创建容器后就退出，但它退出后容器进程的父进程会变成谁？如果回到 dockerd，又回到上面的耦合问题。

### 解法：containerd-shim

containerd 为**每个容器**fork 一个 **containerd-shim** 进程，作为容器主进程的**父进程**：

```
containerd ─── shim(容器A) ─── 容器A 的 PID 1 进程
          └── shim(容器B) ─── 容器B 的 PID 1 进程
```

shim 带来的三大好处：

1. **解耦守护进程**：containerd 重启，容器**不受影响**——因为容器的父进程是 shim，不是 containerd。shim 通过容器运行时（runc）创建容器后接管，独立存活。
2. **接管 runc 的退出**：runc `create` + `start` 完容器就退出，shim 继续做容器进程的父进程，负责 reap 子进程、转发信号、收集退出码、上报状态给 containerd。
3. **隔离故障**：一个容器的 shim 崩溃只影响那个容器，不会拖垮整个 containerd 或其他容器。

> 不同低层运行时有不同 shim：`containerd-shim-runc-v2`（runc）、`containerd-shim-runsc-v1`（gVisor）、`containerd-shim-kata-v2`（Kata）。containerd 通过 shimbinary 名字 + OCI runtime 配置选择。换沙箱运行时 = 换 shim + 换 runtime。

### shim 还做：TTRPC 通信、PTY、日志

shim 通过 **ttrpc**（一个精简的 gRPC 变体）与 containerd 通信，还负责：

- 转发容器的 stdout/stderr 到日志驱动（K8s 里就是 `docker log` / `kubectl logs` 的来源）；
- 处理 exec（`kubectl exec` 进容器，shim 帮你 setns + 启动新进程）；
- 上报容器状态（`kubectl describe` 的 Running/Exited 来自 shim）。

## 3.6 低层运行时：runc（OCI Runtime Spec 实现）

最底层的 runc 是**薄而稳定**的——它只做一件事：**给我一个 OCI bundle（config.json + rootfs），我把它变成运行中的容器**。

### runc 的输入：OCI bundle

```
my-bundle/
├── config.json     ← runtime-spec 配置：要哪些 namespace、cgroup、mounts、capabilities、进程
└── rootfs/         ← 拼好的根文件系统（containerd 的 snapshotter 提供）
```

### runc 的命令（runtime-spec 定义）

```bash
runc create my-container   # 创建容器进程（namespace/cgroup/mount 都设好），但不启动用户进程；shim 接管
runc start  my-container   # 启动用户进程（exec）
runc state  my-container   # 查询状态
runc exec   my-container -- /bin/sh    # 在容器里再起进程（setns）
runc kill   my-container KILL          # 发信号
runc delete my-container               # 清理
```

### runc 内部：libcontainer

runc 的核心是 **libcontainer**（Go 包）——它直接调用内核 API 实现 namespace/cgroup/mount/capabilities，不依赖 LXC（这是 Docker 早期从 LXC 换成自研运行时的产物）。libcontainer 是第 6 章源码分析的重点。

> runc 本身**不碰镜像、不碰 CRI、不碰网络插件**——它是个"纯执行器"。这让 OCI Runtime Spec 极度稳定（自 2015 几乎没大变），上层却可以快速演进。

### 同层替代：crun / youki

因为 runc 只认 OCI bundle，**换低层运行时不影响上层**：

- **crun**（C）：Red Hat 主导，二进制 < 1MB（runc 几十 MB），启动更快、内存占用更小，是 CRI-O 的可选默认。
- **youki**（Rust）：主打内存安全（Rust 无 buffer overflow 类漏洞），适合安全敏感场景。

## 3.7 镜像构建子系统：BuildKit

构建镜像不是运行时主链路的一部分，而是**独立的旁挂子系统**。现代 Docker 构建默认走 **BuildKit**（`moby/buildkit`）：

- **并发构建独立 stage**（多阶段构建的各阶段并行）；
- **更好的缓存**（细粒度层缓存、远程缓存、`--cache-from`）；
- **多架构构建**（`docker buildx build --platform linux/amd64,linux/arm64`，一次构建多架构 manifest list）；
- **可扩展 frontend**（不止 Dockerfile——BuildKit 支持 Cloud Native Buildpacks、Rocky、自定义 frontend）；
- **无 root 构建**（rootless buildkit）。

> `docker build` 在新版 Docker 里默认就是 BuildKit（`DOCKER_BUILDKIT=1`）。`docker buildx` 是 BuildKit 的增强 CLI。BuildKit 与运行时解耦——它只产镜像，怎么跑是运行时的事。

## 3.8 镜像分发子系统：Registry（OCI Distribution Spec）

镜像的"仓库"由 **OCI Distribution Spec** 规定。一个 registry 提供 REST API：

- `GET /v2/<name>/manifests/<reference>`：取 manifest（reference 可以是 tag 或 digest）；
- `GET /v2/<name>/blobs/<digest>`：取某个层/配置的内容；
- `PUT ...`：push 镜像。

公共 registry：**Docker Hub**、**GitHub Container Registry (GHCR)**。私有/自建：**Harbor**（CNCF，企业级，带扫描/签名/复制/多租户）、各云厂商（AWS ECR / Aliyun ACR / GCR）。registry + 内容寻址层 = 镜像的"可分发"性质落地。

## 3.9 CRI 插件：把 containerd 接进 Kubernetes

containerd 进程内内置一个 **CRI plugin**（不是独立进程，是 containerd 启动时加载的插件）。它实现 K8s 的 CRI gRPC 接口，让 kubelet 能这样用它：

```
kubelet ──CRI gRPC──▶ containerd (CRI plugin)
                         ├─ RunPodSandbox()   → 创建 Pod 沙箱（Pod 级 namespace/cgroup）
                         ├─ CreateContainer()  → 拉镜像→解包→创建容器
                         ├─ StartContainer()
                         ├─ StopContainer()
                         ├─ RemovePodSandbox()
                         ├─ ListPodSandbox() / ContainerStatus()
                         └─ PullImage() / ListImages()
```

> **Pod ≠ 容器**：CRI 里 Pod 是一个"沙箱（sandbox）"——一个 Pod 内多个容器共享同一个 net/ ipc namespace（Pause 容器持有这些 namespace，业务容器加入它）。这就是为什么一个 Pod 里的容器能通过 localhost 互通、共享网络栈。Pause 容器（`registry.k8s.io/pause`）是 K8s/CRI 的一个关键设计细节。

## 3.10 端到端全景：一条命令穿过的全部组件

把上述组件串起来，`docker run nginx`（在装了 Docker 的机器上）的全链路是：

1. `docker` CLI 把命令转成对 `dockerd` 的 REST 调用。
2. `dockerd` 调用 `containerd`（gRPC）。
3. `containerd` 的 **Image Service** 检查本地有没有 `nginx` 镜像；没有 → **Transfer Service** 从 registry 拉 manifest → 逐层拉 blobs 到 **Content Store**（按 digest 去重）。
4. **Snapshotter**（overlayfs）把只读层解包成快照树，准备 rootfs。
5. containerd fork 一个 **containerd-shim-runc-v2** 进程。
6. shim 调用 **runc create**：runc/libcontainer 读 OCI config.json → `clone(CLONE_NEWPID|NEWNET|...)` 创建 namespace → 设 cgroup → 挂载 rootfs → 创建容器进程（但不启动用户命令）。
7. shim 调用 **runc start**：`exec` 用户进程（nginx）。
8. 容器进入 Running；shim 持续 reap 子进程、转发日志、上报状态给 containerd。

在 **K8s 节点**上，步骤 1-2 替换为"kubelet 通过 CRI 调 containerd"，其余完全一样。这就是为什么"理解容器运行时"能让你在 K8s 和纯 Docker 两个场景里都受益——底层是同一套东西。

## 本章小结

现代容器运行时是一条**严格分层、各司其职**的调用链：用户接口（docker/nerdctl/crictl）→ 可选的 Docker Engine（dockerd，开发/构建用）→ **containerd**（高层运行时，含 Image/Content/Snapshotter/CRI/Transfer 等解耦子系统）→ **containerd-shim**（每容器一个，把守护进程与容器解耦，runc 退出后接管容器）→ **runc/libcontainer**（低层运行时，真正调内核 clone/cgroup/mount 创建隔离进程）→ Linux 内核。旁挂的 **BuildKit** 负责把 Dockerfile 变成镜像，**registry** 负责镜像分发，两者都与运行时解耦。这套分层的关键价值是**可替换**：换高层运行时（containerd↔CRI-O）或换低层运行时（runc↔crun↔kata 做沙箱）都不影响其他层——这正是 OCI 标准化的红利。下一章我们用一个具体命令的完整生命周期，把这条架构走一遍时序。

**参考来源**

- [containerd ARCHITECTURE.md](https://github.com/containerd/containerd/blob/main/docs/ARCHITECTURE.md)
- [containerd 架构图（官方 docs）](https://github.com/containerd/containerd/blob/main/docs/ARCHITECTURE.md)
- [containerd-shim 设计](https://github.com/containerd/containerd/blob/main/runtime/README.md)
- [OCI Runtime Specification（命令与 bundle）](https://github.com/opencontainers/runtime-spec)
- [runc 仓库](https://github.com/opencontainers/runc)
- [BuildKit](https://github.com/moby/buildkit)
- [Kubernetes CRI（Container Runtime Interface）](https://kubernetes.io/zh-cn/docs/concepts/architecture/cri/)
- [Harbor（企业级 registry）](https://goharbor.io/)
