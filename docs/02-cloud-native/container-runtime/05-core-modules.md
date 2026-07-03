# 5. 核心模块：镜像、快照、shim、CRI、Transfer

> 一句话理解：本章逐一深入容器运行时的核心模块——**镜像的数据结构**（manifest/config/layers/index）、**Content Store**（按 digest 存 blob）、**Snapshotter**（overlayfs 快照树）、**containerd-shim**（每容器父进程）、**runc/libcontainer**（实际创建）、**CRI 插件**（对接 K8s）、**Transfer Service**（流式传输）、**NRI**（运行时插件），每个模块讲清"它管什么数据、暴露什么接口、可怎么替换"。

## 5.1 镜像的数据结构（OCI image-spec 四件套）

理解运行时的前提，是理解它操作的对象——**镜像**。OCI image-spec 定义镜像由四种 JSON blob 组成，全部按 digest 寻址、存在 Content Store：

### （1）config（镜像配置）

描述"这个镜像怎么跑"：

```jsonc
{
  "architecture": "amd64",
  "os": "linux",
  "config": {
    "User": "101:101",
    "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "PYTHON_VERSION=3.11"],
    "Entrypoint": ["python3"],
    "Cmd": ["app.py"],
    "WorkingDir": "/app",
    "ExposedPorts": { "8000/tcp": {} },
    "Volumes": { "/data": {} }
  },
  "rootfs": {
    "type": "layers",
    "diff_ids": ["sha256:<uncompressed-layer-1-digest>", "sha256:<uncompressed-layer-2-digest>", ...]
  },
  "history": [ { "created": "...", "created_by": "/bin/sh -c apt install -y ..." }, ... ]
}
```

两个要点：

- **`rootfs.diff_ids` 是层的未压缩摘要**——而 manifest.layers 里的 digest 是**压缩后**的摘要。运行时需要解压层、用 diff_id 校验解压后内容的完整性（拉到压缩 blob → 解压 → SHA256 应等于 diff_id）。
- **`history`** 记录每层是哪条 Dockerfile 指令产生的——`docker history` 命令的来源，也用于判断哪些层是"空的"（如 `ENV` 不产生层但仍记录 history）。

### （2）manifest（单架构清单）

列出 config + layers（见第 4 章示例）。它是镜像的"目录页"。

### （3）layers（文件系统层）

每层是一个 **tar 归档的压缩包**（gzip / zstd）。层之间是**增量**的——上层记录相对下层的文件增删改（删除用 whiteout 文件标记）。Snapshotter 解包时按顺序叠加。

### （4）image index / manifest list（多架构索引）

```jsonc
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.index.v1+json",
  "manifests": [
    { "mediaType": "...manifest.v1+json", "digest": "sha256:<amd64>", "platform": {"os":"linux","architecture":"amd64"} },
    { "mediaType": "...manifest.v1+json", "digest": "sha256:<arm64>", "platform": {"os":"linux","architecture":"arm64","variant":"v8"} }
  ]
}
```

### image-spec v1.1 新增：subject / referrers

v1.1（2023/2024）给 manifest 加了 **`subject`** 字段——允许一个"附属 manifest"声明它指向另一个镜像。配合 registry 的 **referrers API**，可以给镜像挂载：

- **签名**（cosign 签名作为一个独立 manifest，subject 指向被签镜像）；
- **SBOM**（软件物料清单）；
- **attestation**（provenance、漏洞扫描结果）。

这是"镜像供应链安全"的标准基础设施（第 8 章详述）——不需要改被签镜像本身，签名/SBOM 作为可发现的附属物。

## 5.2 Content Store：按 digest 存 blob

Content Store 是 containerd 存**镜像原始内容**的地方——manifest、config、各层 tar.gz，**全部按内容的 SHA256 digest 寻址存储**。

```
Content Store
├─ sha256:<config-digest>   → config JSON
├─ sha256:<layer-1-digest>  → layer-1.tar.gz
├─ sha256:<layer-2-digest>  → layer-2.tar.gz
└─ sha256:<manifest-digest> → manifest JSON
```

性质：

- **去重**：digest 相同的内容只存一份。两个共享 base 层的镜像共用一个 blob。
- **内容寻址**：digest 即地址，digest 一致即内容一致（完整性校验天然成立）。
- **不可变**：内容一旦写入不再修改。
- **GC（垃圾回收）**：通过 **lease（租约）**机制管理引用——镜像被某个容器引用时持有 lease，不会被回收；无引用的 blob 才被清理。

> 用 `ctr content list` 可以看 containerd 的 Content Store 内容。排查"为什么磁盘被镜像占满"时，这是入口。

## 5.3 Snapshotter：从 blob 到可挂载的 rootfs

Content Store 里是压缩归档，运行容器要的是**解开的文件系统**。**Snapshotter** 负责这个转换，并把多个层组织成可联合挂载的快照树。

### 快照的三种状态

每个快照（snapshot）有三种状态：

- **Committed（已提交）**：只读快照，对应镜像的一个层（已解包）。可以被多个上层共享。
- **Active（活动）**：可读写快照。容器运行时用这个（COW 的 upperdir）。
- **View（视图）**：只读快照，但建立在已提交快照之上（用于只读挂载，如构建时读层）。

### 关键操作

```go
// snapshotter 接口（简化）
type Snapshotter interface {
    Prepare(key, parent string, opts...) (Mounts, error)   // 在 parent 上创建可写 active 快照
    Commit(name, key string, opts...) error                // 把 active 提交为只读 committed
    Mounts(key string) (Mounts, error)                      // 取挂载点
    Remove(key string) error                                // 删除
    Stat(key string) (Info, error)                          // 查状态
    Walk(fn func(Info) error) error                         // 遍历
}
```

拉取镜像时，对每个层：`Prepare`（在父快照上建可写）→ 解压层内容写入 → `Commit`（固化为只读，成为下一层的父）。

### 默认实现 overlayfs

overlayfs snapshotter 把 committed 快照的目录作为 **lowerdir**，active 快照作为 **upperdir**，返回 overlay mount 命令给上层。最终的 rootfs 挂载点交给 runc（`config.json` 的 `root.path`）。

### 可替换性：stargz / nydus / btrfs

Snapshotter 是**接口**，可替换（见第 4 章）。惰性拉取（stargz/nydus）就是换 snapshotter——它不在拉取阶段全解包，而是把层存为特殊格式，运行时按需从 registry 读文件。

## 5.4 containerd-shim：每容器一个的"代理父进程"

第 3 章讲了 shim 存在的理由（解耦守护进程、接管 runc 退出），这里讲它的**接口与实现**。

### shim 的二进制命名约定

containerd 通过约定找到对应 shim：

- `io.containerd.runc.v2` → `containerd-shim-runc-v2`（runc 默认）
- `io.containerd.runsc.v1` → `containerd-shim-runsc-v1`（gVisor）
- `io.containerd.kata.v2` → `containerd-shim-kata-v2`（Kata）

换运行时 = 换 shim binary + containerd 配置 `default_runtime`。

### shim manager（v2 shim）

containerd 的 **shim v2** 统一了接口——所有 shim 实现同一组 ttrpc 方法（`Create`/`Start`/`Delete`/`Exec`/`Pids`/`Wait`）。这让 containerd 用同一套逻辑管理 runc/gVisor/Kata 容器。

### shim 与日志

shim 把容器的 stdout/stderr 写到 **containerd 的日志管道**，K8s kubelet 再从管道读出来交给日志驱动（这就是 `kubectl logs` 的链路）。`--log-driver json-file`/`journald`/`fluentd` 等 Docker 日志驱动在容器层就由 shim 实现。

## 5.5 runc / libcontainer：真正的"执行器"

runc 是运行时的"最后一公里"——所有抽象（镜像、快照、CRI）到这里都变成**具体的系统调用**。runc 的核心是 Go 包 **libcontainer**（不再依赖 LXC，直接调内核）。

### libcontainer 做的事（对应 runc create）

```go
// 概念性伪代码（非真实代码）
func (c *linuxContainer) Start(process *Process) error {
    // 1. 准备 rootfs（来自 config.json 的 root.path，snapshotter 已备好）
    // 2. 设置 rootless / cgroup 模式（v1/v2）
    // 3. clone 出容器进程，传入配置好的 namespace
    parentPid, err := c.creator.Create(process, c.config)   // fork + CLONE_NEW*
    // 4. 在容器进程内：
    //    - setup cgroup（写 /sys/fs/cgroup/.../cgroup.procs）
    //    - 挂载 rootfs + /proc + /sys + /dev
    //    - pivot_root 切换根目录
    //    - drop capabilities + 应用 seccomp + AppArmor
    //    - sethostname / set network
    //    - exec 用户命令
    // 5. 容器进程成为 PID 1，shim 成为它的宿主侧父进程
}
```

### 关键内核调用

| 操作 | 系统调用 / 机制 |
|---|---|
| 创建 namespace | `clone(CLONE_NEWPID\|CLONE_NEWNET\|...)` 或 `unshare` |
| 加入已有 namespace | `setns`（exec 进容器用） |
| 切换根目录 | `pivot_root(2)`（比 chroot 更彻底，配合 mount namespace） |
| 设 cgroup | 写 `/sys/fs/cgroup/.../cgroup.procs` 等 cgroupfs 文件 |
| 收窄权限 | `capset`（capabilities）、prctl `PR_SET_NO_NEW_PRIVS`、seccomp BPF |

> libcontainer 是第 6 章源码分析的重点——它是"OCI Runtime Spec 是如何用 Go 落地成系统调用"的最佳教材。

### runc 的对手：crun / youki

- **crun**（C）：更小的二进制、更低的内存、更快的启动（对高密度节点有意义）。CRI-O 常配 crun。
- **youki**（Rust）：内存安全（杜绝 C/Go 罕见但仍可能的内存漏洞类风险）。

因为都实现 OCI Runtime Spec，上层无感知地切换。

## 5.6 CRI 插件：containerd 与 K8s 的桥梁

CRI 插件**内置在 containerd 进程内**（containerd 启动时加载），实现 K8s 的两个 gRPC service：

### RuntimeService（容器/Pod 生命周期）

```protobuf
service RuntimeService {
  rpc RunPodSandbox(PodSandbox) returns (...)         // 创建 Pod 沙箱（pause 容器 + namespace + CNI）
  rpc StopPodSandbox(...) returns (...)
  rpc RemovePodSandbox(...) returns (...)
  rpc ListPodSandbox(...) returns (...)

  rpc CreateContainer(...) returns (...)              // 创建业务容器（加入 pause 的 namespace）
  rpc StartContainer(...) returns (...)
  rpc StopContainer(...) returns (...)
  rpc RemoveContainer(...) returns (...)
  rpc ListContainers(...) returns (...)
  rpc ContainerStatus(...) returns (...)
  rpc ExecSync(...) returns (...)                     // kubectl exec / 健康检查 exec
}
```

### ImageService（镜像管理）

```protobuf
service ImageService {
  rpc ListImages(...) returns (...)
  rpc ImageStatus(...) returns (...)
  rpc PullImage(...) returns (...)
  rpc RemoveImage(...) returns (...)
  rpc ImageFsInfo(...) returns (...)                  // 节点镜像存储用量
}
```

### Pod 沙箱的关键：Pause 容器

`RunPodSandbox` 实际是创建一个 **pause 容器**（`registry.k8s.io/pause`），它：

1. 创建一组 net/ipc namespace（pause 进程持有它们）；
2. CNI 插件给这个 net namespace 分配 Pod IP、配网卡；
3. 后续业务容器 `CreateContainer` 时，被配置为**加入 pause 的 net/ipc namespace**。

这样：业务容器重启，pause 还在，Pod IP 不变；同 Pod 容器 localhost 互通。

> CRI-O 与 containerd 的 CRI 插件实现不同（CRI-O 用 conmon 做部分 shim 职责），但接口相同——K8s 不感知差异。

## 5.7 Transfer Service：流式镜像传输（containerd 2.x）

containerd 2.x 把镜像 pull/push 重构为 **Transfer Service**——一个**流式**接口：

- **Streaming**：不再一次性"下载整个镜像"，而是用流式 progress + 可恢复；
- **可扩展进度/认证/重试**：上层（K8s、CRI）能拿到细粒度进度；
- **原生支持惰性拉取**：与 stargz/nydus snapshotter 深度集成，镜像未下完即可启动；
- **统一 pull/push 路径**：之前的 puller/pusher 分散在多处，Transfer Service 统一了。

> 对大镜像（几十 GB 的模型镜像），Transfer Service + stargz 是冷启动优化的关键组合——这直接影响 AI 推理服务的弹性扩缩速度。

## 5.8 NRI（Node Resource Interface）：运行时插件

**NRI** 是 containerd/CRI-O 共同支持的**运行时插件接口**，允许第三方在容器创建时介入——典型用途：

- **GPU/设备注入**：NVIDIA 的 GPU Operator 通过 NRI 注入 GPU 设备、环境变量；
- **资源调整**：在容器创建时动态改 cgroup；
- **sidecar 注入**：服务网格（Istio）的 sidecar 注入有部分路径走 NRI；
- **安全策略**：强制 seccomp/capabilities 收窄。

NRI 弥补了"静态 CRI"的不足——CRI 调用是声明式的，但有时需要在容器真正创建的瞬间做干预，NRI 提供了这个 hook。

## 5.9 模块全景与数据流

把模块和数据流画在一起：

```
                    kubelet (CRI)            nerdctl/docker (gRPC)
                         │                          │
                         ▼                          ▼
   ┌──────────────── CRI plugin / containerd API ──────────────────┐
   │                                                                 │
   │   Image Service  ──▶  Content Store ◀── Transfer Service(registry)
   │        │                  │ (blobs, digest)        pull/push    │
   │        ▼                  ▼                                     │
   │   Snapshotter ◀── 解包层 ─┘                                     │
   │   (overlayfs)        │                                          │
   │   快照树 → rootfs    │                                          │
   │                      ▼                                          │
   │   shim manager ──▶ fork shim ──▶ runc create ──▶ runc start     │
   └─────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                       Linux Kernel
```

每个箭头都是一个可替换、可观测的接口——这正是容器运行时"分层 + 标准"设计的全貌。

## 本章小结

容器运行时的核心模块围绕"把镜像变成进程"的数据流组织：**镜像**是 manifest（目录）+ config（怎么跑）+ layers（文件系统增量）+ index（多架构）四件套，image-spec v1.1 的 `subject`/referrers 让签名/SBOM 可作为附属物挂载；**Content Store** 按 digest 去重存储这些 blob；**Snapshotter** 把压缩层解包成 committed 快照、组成父子链、用 overlayfs 联合挂载出 rootfs（可替换为 stargz/nydus 做惰性拉取）；**containerd-shim** 作为每容器父进程，解耦守护进程、接管 runc 退出后的 reap/日志/信号/exec；**runc/libcontainer** 是真正的执行器，把 OCI config 翻译成 clone/cgroup/mount/capabilities 系统调用；**CRI 插件**让 containerd 被 kubelet 调用（RunPodSandbox 用 pause 容器持有 Pod namespace）；**Transfer Service**（2.x）做流式镜像传输、支持惰性拉取；**NRI** 提供容器创建时的插件 hook。理解每个模块"管什么、暴露什么、可怎么换"，你就能在面对"换 GPU 注入方式""换沙箱运行时""优化大镜像冷启动"这类需求时，知道该动哪一层。

**参考来源**

- [OCI Image Specification（manifest/config/layers/index）](https://github.com/opencontainers/image-spec/blob/main/spec.md)
- [OCI Image Spec v1.1（subject/referrers）](https://github.com/opencontainers/image-spec/blob/main/manifest.md)
- [containerd Content / Snapshotter 接口](https://github.com/containerd/containerd/blob/main/docs/snapsholders.md)
- [containerd Shim v2](https://github.com/containerd/containerd/blob/main/runtime/v2/README.md)
- [NRI（Node Resource Interface）](https://github.com/containerd/nri)
- [Kubernetes CRI API](https://github.com/kubernetes/cri-api)
- [crun 仓库](https://github.com/containers/crun) / [youki 仓库](https://github.com/containers/youki)
