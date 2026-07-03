# 6. 源码分析：runc、containerd、moby 的实现

> 一句话理解：本章带你走进三个开源仓库——**`opencontainers/runc`**（OCI Runtime Spec 的参考实现，核心是 Go 包 libcontainer，把 config.json 翻译成 clone/cgroup/mount 系统调用）、**`containerd/containerd`**（高层运行时，含 CRI 插件、snapshotter、shim）、**`moby/moby`**（Docker Engine 开源上游，历史角色）。读完本章你能从一条 `runc start` 命令一路追到内核系统调用，从 containerd 的 gRPC handler 追到 snapshotter 的 overlay 挂载。

## 6.1 总览：三个仓库的分工

| 仓库 | 角色 | 语言 | 体量 | 阅读价值 |
|---|---|---|---|---|
| `opencontainers/runc` | OCI Runtime Spec 参考实现（低层运行时） | Go | 中（约 5 万行核心） | **最高**——容器本质的系统调用实现 |
| `containerd/containerd` | 高层运行时（镜像/快照/shim/CRI） | Go | 大（>50 万行） | 高——理解容器管理全貌 |
| `moby/buildkit` | 镜像构建引擎 | Go | 大 | 中——Dockerfile → 镜像 |
| `moby/moby` | Docker Engine（dockerd）开源上游 | Go | 大 | 低（已基本被 containerd 取代） |
| `containers/crun` | crun（C 实现的低层运行时） | C | 小 | 中——对照 runc 看 C 实现 |

> 阅读建议：**先读 runc**（小而精华，能看到容器的"原子操作"），**再读 containerd**（理解编排如何调度运行时）。`moby/moby` 仅在研究历史/兼容性时翻。

## 6.2 runc：从命令到内核的完整链路

### 仓库结构（runc 1.2.x）

```
runc/
├── cmd/runc/                ← CLI 入口（main.go + 各子命令）
│   ├── main.go
│   ├── create.go            ← runc create
│   ├── start.go             ← runc start
│   ├── exec.go              ← runc exec
│   ├── kill.go / delete.go / state.go / list.go / run.go / spec.go
├── libcontainer/            ← 核心库（runc 的"灵魂"）
│   ├── container.go         ← Container 接口与实现
│   ├── process.go           ← Process（容器内的进程抽象）
│   ├── factory.go           ← 创建 Container 的工厂
│   ├── rootfs_linux.go      ← rootfs 挂载 + pivot_root（Linux 专属）
│   ├── namespaces/          ← namespace 创建/进入
│   ├── cgroups/             ← cgroup v1/v2 管理
│   │   ├── fs2/             ← cgroup v2
│   │   ├── fs/              ← cgroup v1
│   │   └── systemd/         ← systemd 驱动
│   ├── mounts/              ← mount 操作
│   ├── security/            ← capabilities / seccomp / apparmor
│   ├── system/              ← 直接的系统调用封装
│   ├── configs/             ← config.json 的 Go 结构（runtime-spec）
│   └── utils/
├── libcontainer/...linux*.go ← Linux 专属实现（rootfs_linux.go 等）
├── script/                  ← 测试/发布脚本
└── tests/                   ← 集成测试（含 OCI conformance）
```

> 注意：runc 的"跨平台"是文件后缀分的——`*_linux.go` 是 Linux 实现，`*_freebsd.go`/`*_windows.go` 等是其他平台（runc 也支持有限的其他 OS，但容器核心是 Linux）。Go 编译器按平台只编对应文件。

### 入口：`cmd/runc/main.go` → 各子命令

`runc` CLI 用 `urfave/cli` 框架。`runc create` 的命令处理在 `cmd/runc/create.go`，它解析 bundle 路径、读 `config.json`，然后调用 libcontainer。

```go
// cmd/runc/create.go（概念性简化）
func createAction(context *cli.Context) error {
    container, err := libcontainer.New(context.String("root"))   // 创建 factory
    // ...
    config := loadConfig(bundlePath)                              // 读 config.json
    c, err := container.Create(id, config)                        // 创建 Container（不启动）
    // containerd-shim 实际是先 create 再 start 的协调者
}
```

### 核心链：`Container.Create` → 启动"init 进程"

libcontainer 的核心是创建一个**特殊的"init 进程"**——它运行 runc 自己的 init 代码（不是用户的命令），在 init 代码里完成所有隔离设置，最后才 exec 用户命令。

```go
// libcontainer/container_linux.go（概念性简化）
func (c *linuxContainer) Start(process *Process) error {
    // 1. 准备一个 parent process（用 os/exec）
    p := c.initProcess(...)                  // c.initProcess 是 *initProcess
    // 2. clone 出子进程，传入 namespace flags
    return p.start()                          // 真正 fork + 配置
}
```

`initProcess.start()` 用 Go 的 `os/exec` + `exec.Cmd.SysProcAttr` 设置 clone flags：

```go
// libcontainer/process_linux.go（概念性简化）
cmd := exec.Command("/proc/self/exe", "init")          // 重新 exec runc 自己的 init
cmd.SysProcAttr = &syscall.SysProcAttr{
    Cloneflags: syscall.CLONE_NEWPID | syscall.CLONE_NEWNS |
                syscall.CLONE_NEWNET | syscall.CLONE_NEWIPC |
                syscall.CLONE_NEWUTS | syscall.CLONE_NEWUSER,
    // ... uid/gid 映射（user namespace）
}
```

> **关键技巧**：runc 通过 `/proc/self/exe init` **重新执行自己**（即 `runc init` 子命令），让那个新进程在新的 namespace 里完成"初始化"，最后 `exec` 用户命令。这种 "re-exec self as init" 模式是很多容器运行时的通用手法。

### init 进程内：rootfs + cgroup + 权限收窄

新进程进入新 namespace 后，runc 的 init 代码（`libcontainer/factory_linux.go` → `init`）依次：

1. **设置 cgroup**：把自己加入 `config.Linux.CgroupsPath`（cgroupfs 或 systemd）。
2. **挂载并切换 rootfs**（`rootfs_linux.go`）：
   - 挂载 config 里所有 `mounts`（`/proc`、`/sys`、`/dev`、bind mounts 等）；
   - **`pivot_root`**（比 `chroot` 更彻底——`pivot_root` 改变整个 mount namespace 的根，配合 mount namespace 才能真正隔离；`chroot` 只改进程的根视图，不安全）；
3. **收窄权限**（`security/`）：
   - `capset`：drop 所有 capability，只留 config 允许的；
   - seccomp：加载 BPF 过滤器，禁用危险系统调用；
   - AppArmor/SELinux profile（若配置）。
4. **hostname / network / rlimit / oom_score_adj** 等杂项。
5. **`exec` 用户命令**（`syscall.Exec`）——进程镜像替换为用户命令（如 `nginx`），成为容器 PID 1。

> **pivot_root vs chroot**：这是面试常考点。`chroot` 只改进程的 `/` 视图，但进程仍能通过某些方式访问原文件系统；`pivot_root` 在 mount namespace 里把根**整体换掉**，旧根被卸载，隔离更彻底。容器用 pivot_root。

### cgroup 管理：`libcontainer/cgroups/`

runc 抽象了 cgroup manager 接口，两个实现：

- **cgroup v2（`fs2/`）**：写 `/sys/fs/cgroup/<path>/` 下的文件（`cgroup.procs`、`memory.max`、`cpu.max`、`pids.max`…）。
- **systemd（`systemd/`）**：通过 systemd DBus 创建 slice/scope，让 systemd 管 cgroup（K8s 默认用 systemd 驱动，与 kubelet 一致）。

> cgroup manager 的选择在 `config.json` 的 `linux.cgroupsPath` + 运行时配置里决定。K8s 节点上 containerd/runc 通常配 `SystemdCgroup = true`，与 kubelet 一致——这是生产配置的硬要求（不一致会导致 cgroup 路径混乱、监控失效）。

### 测试：OCI conformance

runc 的 `tests/` 有 OCI Runtime Spec 的一致性测试——验证 runc 的行为符合规范（任何 OCI bundle 都应正确运行）。这是 OCI 标准的可执行保证。

## 6.3 containerd：高层运行时的源码地图

### 仓库结构（containerd 2.x）

containerd 2.x 重构了目录（从 1.x 的扁平 `pkg/` 重组成 `core/` + `cmd/` + `internal/` + `api/` + `plugins/`）：

```
containerd/
├── cmd/
│   ├── containerd/              ← containerd 主进程入口（main.go）
│   ├── containerd-shim-runc-v2/ ← shim v2 入口
│   └── ctr/                     ← ctr CLI（containerd 原生调试）
├── core/                        ← 核心抽象与运行时
│   ├── runtime/                 ← runtime 接口、shim 管理
│   ├── containers/              ← Container 元数据
│   ├── content/                 ← Content Store（按 digest 存 blob）
│   ├── images/                  ← Image 元数据
│   ├── snapshots/               ← Snapshotter 接口
│   ├── mount/                   ← mount 操作
│   ├── diff/                    ← 层 diff（构建时用）
│   └── leases/                  ← 引用计数（GC 依据）
├── api/                         ← gRPC/protobuf 定义（containerd 服务接口）
│   └── services/                ← 各 service 的 proto
├── plugins/                     ← 具体插件实现
│   ├── content/                 ← Content Store 的本地实现
│   ├── snapshotter/overlayfs/   ← overlayfs snapshotter
│   ├── image/                   ← Image Service
│   ├── runtime/v2/              ← shim v2 runtime
│   ├── cri/                     ← CRI 插件（重要！）
│   ├── transfer/                ← Transfer Service
│   └── ...
├── pkg/                         ← 工具包
└── integration/                 ← 集成测试
```

### 主进程入口：`cmd/containerd/main.go`

containerd 启动时：

1. 解析配置（`config.toml`）——决定加载哪些插件、监听哪些 socket（`/run/containerd/containerd.sock`）、用什么 runtime、snapshotter。
2. **初始化服务网格**（containerd 用 **`go-plugin` / 内置 plugin 注册**机制）：按依赖顺序加载所有插件（content → snapshotter → image → runtime → cri → transfer…）。
3. 起 gRPC server，注册各 service。

> containerd 的"插件化"是它可裁剪的根基——`config.toml` 里可以禁用某些插件（如非 K8s 场景禁用 CRI）。

### 关键调用链：一次 `PullImage`

```
ctr/images.go / CRI PullImage
  → ImageService.PullImage()              （plugins/image/）
    → Transfer Service（plugins/transfer/，2.x）
      → Resolver → HTTP 拉 manifest + blobs
      → 写入 Content Store（plugins/content/）
    → 解析 manifest → 注册 Image 元数据（images table）
```

### 关键调用链：一次 `CreateContainer` + `Start`

```
containerd API Create → Containers Service 创建元数据（containers table）
                     → Snapshotter.Prepare()（plugins/snapshotter/overlayfs/）
                         → 解包所需层 → 生成 rootfs 挂载点
                     → 生成 OCI config.json（基于镜像 config + 运行时参数）

containerd API Start → Runtime Service（core/runtime/）
  → shim manager fork containerd-shim-runc-v2
  → shim.Create() → shim 调 runc create
                  → runc/libcontainer clone + cgroup + mount + pivot_root
  → shim.Start() → shim 调 runc start → exec 用户进程
```

### CRI 插件：`plugins/cri/`

CRI 插件实现 K8s 的 `RuntimeService` + `ImageService`：

- `plugins/cri/server/`：gRPC handler（RunPodSandbox、CreateContainer…）。
- `plugins/cri/containerd/`：把 CRI 语义翻译成 containerd 原生操作（Pod 沙箱 = 特殊容器 + 标签）。
- 关键逻辑：**`CreateContainer` 时把业务容器的 config 改为加入 pause 容器的 net/ipc namespace**（通过读取 Pod 沙箱的 namespace 路径，填进 OCI config 的 `namespaces`）。

### snapshotter 实现：`plugins/snapshotter/overlayfs/`

overlayfs snapshotter 的核心是把 committed 快照目录作为 lowerdir、active 作为 upperdir，返回一条 overlay mount 命令：

```go
// 概念性
func (o *snapshotter) Mounts(key string) ([]mount.Mount, error) {
    // 收集 key 的父链上所有 committed 快照的路径作为 lowerdir
    lowerdirs := parentsDirs(s)
    upperdir := s.activePath
    workdir := s.workPath
    return []mount.Mount{{
        Type: "overlay",
        Source: "overlay",
        Options: []string{
            "lowerdir=" + strings.Join(lowerdirs, ":"),
            "upperdir=" + upperdir,
            "workdir=" + workdir,
        },
    }}, nil
}
```

这就是 `mount -t overlay overlay -o lowerdir=...:...,upperdir=...,workdir=...` 的 Go 落地——也是 Snapshotter 接口最薄的部分。

## 6.4 containerd-shim：`cmd/containerd-shim-runc-v2/`

shim v2 的入口是 `containerd-shim-runc-v2` 二进制（每容器一个进程）。它的职责（实现 shim v2 ttrpc 接口）：

- `Create`：调 `runc create`，建立容器；
- `Start`：调 `runc start`，启动用户进程；
- `Exec`：处理 `runc exec`（kubectl exec 进容器）；
- `Pids`：列容器内进程；
- `Wait`：等待容器退出，返回 exit code；
- 日志管道：把容器 stdout/stderr 转发给 containerd。

shim 本身是个**长期运行的小进程**（每个容器一个），它通过 ttrpc 与 containerd 双向通信，崩溃时 containerd 能感知（`shim monitor`）并清理孤儿容器。

## 6.5 crun：用 C 实现同一份规范（对照阅读）

`containers/crun` 是 C 写的 OCI 运行时，结构更小：

```
crun/
├── src/
│   ├── crun.c              ← CLI 入口
│   ├── libcrun/            ← 核心库（类似 libcontainer）
│   │   ├── container.c
│   │   ├── linux.c         ← namespace/cgroup/mount
│   │   ├── cgroup.c        ← cgroup v1/v2
│   │   ├── seccomp.c
│   │   └── ...
│   └── ...
```

对照阅读 runc（Go）和 crun（C）对同一份 OCI config 的处理，能看清"OCI 规范与语言无关"的本质——同一个 `config.json`，无论用 Go 还是 C 解析、用 libcontainer 还是 libcrun 落地，最终产生**完全一致**的隔离容器。

> crun 的优势：二进制 ~1MB（runc 含 Go runtime 几十 MB）、启动更快、内存更省。高密度节点（一节点上千容器）这些差异有意义——这也是 CRI-O 倾向配 crun 的原因。

## 6.6 moby/moby：Docker Engine 的历史角色

`moby/moby` 是 Docker Engine（`dockerd`）的开源上游。它的价值现在是**历史与兼容**：

- 早期（2013–2017）它是一个**单体 daemon**，包揽镜像/运行时/网络/卷；
- Docker 把运行时核心剥离成 containerd/runc（捐赠出去）后，dockerd 沦为"在 containerd 之上加一层 Docker 体验"的薄层；
- 在 K8s 节点上 dockerd 已不存在（dockershim 移除）。

阅读价值：理解"为什么社区要拆 Docker"——看 moby/moby 早期的 `daemon/`、`api/`、`builder/`、`network/` 巨大的耦合，对比 containerd 的解耦插件，能深刻体会"分层 + 标准"的工程必要性。

## 6.7 阅读路径建议

按你的目标选路径：

**目标：理解"容器到底怎么隔离的"**
1. `opencontainers/runc` 的 `libcontainer/process_linux.go` + `rootfs_linux.go` + `cgroups/`。
2. 跟 `runc create` → `clone(CLONE_NEW*)` → init 进程内 `pivot_root` + `capset` + seccomp → `exec` 用户命令。
3. 对照 `containers/crun/src/libcrun/linux.c` 看 C 实现。

**目标：理解"containerd 如何管理容器"**
1. `cmd/containerd/main.go` → 看插件加载。
2. `plugins/image/`（镜像服务）+ `plugins/snapshotter/overlayfs/`（快照）。
3. `plugins/cri/server/`（CRI 接口）+ `core/runtime/`（shim 管理）。
4. 跟一次 `PullImage` + `CreateContainer` + `Start`。

**目标：构建/优化镜像**
1. `moby/buildkit`——`cmd/buildctl/`、`frontend/dockerfile/`、`solver/`（构建依赖图与缓存）。
2. 关注 BuildKit 的 `--cache-from`/`--cache-to`（远程缓存）、多阶段并行。

## 本章小结

源码层面，容器运行时是**规范（OCI）+ 实现（runc/containerd）**的典范：**runc/libcontainer** 用 Go 把 OCI config.json 翻译成具体的 `clone(CLONE_NEW*)` + cgroupfs 写入 + `pivot_root` + capabilities/seccomp 收窄 + `exec` 用户命令，是"容器即受约束进程"的最直接证据；**containerd** 用插件化架构把镜像（Content Store）/ 快照（Snapshotter）/ 运行时（shim v2 + runc）/ 编排（CRI 插件）/ 传输（Transfer Service）解耦成可替换的子系统，让 K8s 能通过 CRI 调用它而无需 dockerd；**crun** 用 C 实现同一份规范，证明 OCI 的语言无关性；**moby/moby** 作为历史遗存，提醒我们"为什么要拆"。读完源码，你会对"一条 `docker run` 背后有多少精巧的分层"有肌肉记忆般的理解——这份理解让你在面对任何容器运行时问题（GPU 注入、沙箱、冷启动、cgroup 调优）时，都能找到对应的代码入口。

**参考来源**

- [opencontainers/runc 源码](https://github.com/opencontainers/runc)
- [runc libcontainer 文档](https://github.com/opencontainers/runc/tree/main/libcontainer)
- [containerd/containerd 源码](https://github.com/containerd/containerd)
- [containerd ARCHITECTURE.md](https://github.com/containerd/containerd/blob/main/docs/ARCHITECTURE.md)
- [containerd shim v2](https://github.com/containerd/containerd/blob/main/runtime/v2/README.md)
- [containers/crun 源码](https://github.com/containers/crun)
- [moby/moby（Docker Engine 上游）](https://github.com/moby/moby)
- [moby/buildkit](https://github.com/moby/buildkit)
- [youki（Rust OCI runtime）](https://github.com/containers/youki)
