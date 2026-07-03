# 2. 核心思想：容器不是虚拟机，而是受约束的进程

> 一句话理解：一个容器**就是宿主机上一个普通的进程**——它之所以"看起来"独立，完全是因为它被塞进了一组 Linux **namespace**（看不见别人）、被 **cgroup**（用不了超额资源）、被 **overlayfs**（拿到一份分层拼出的根文件系统）所约束；再叠加一个**不可变、内容寻址、可分发**的镜像格式，和"高层运行时管生命周期 / 低层运行时做创建"的分层——这就是容器的全部核心思想。

## 2.1 容器 vs 虚拟机：本质区别是一句话

这是最容易被误解的概念，必须先讲透：

| 维度 | 虚拟机（VM） | 容器（Container） |
|---|---|---|
| 隔离粒度 | **硬件级**：每个 VM 跑一个完整客户机内核 | **进程级**：所有容器共享宿主机内核 |
| 启动开销 | 秒～分钟（要启动整个内核 + init） | 毫秒～秒（就是 fork/exec 一个进程） |
| 资源开销 | 每个 VM 几 GB 内存起步 | 几 MB（几乎只有进程本身） |
| 隔离强度 | 强（hypervisor 硬件隔离，难逃逸） | 弱～中（共享内核，内核漏洞=全逃逸） |
| 密度 | 一台宿主跑十几个 VM | 一台宿主跑几百个容器 |

**一句话**：**虚拟机虚拟硬件，容器虚拟操作系统视图**。容器没有 hypervisor、没有客户机内核——它就是宿主机内核直接调度的进程，只不过这个进程"看到的"系统（文件系统、进程列表、网络、用户）被 namespace 改写过了。

验证方法：在宿主机上 `docker run -d alpine sleep 1000`，然后在宿主机执行 `ps aux | grep sleep`——你会**看到那个容器进程**，它的 PID 就是宿主机上的某个号。这就证明了"容器即进程"。

> 这个事实是理解一切容器行为的基础：容器的"隔离"是**约定俗成的视图改写**，不是硬件强制。因此**容器隔离弱于虚拟机**——这也是为什么需要 gVisor/Kata 这类沙箱运行时（见第 8 章）来做"容器体验 + VM 级隔离"。

## 2.2 三大基石之一：namespaces —— 隔离"看得见什么"

**namespace** 让一个进程**以为某些全局系统资源是它独占的**。Linux 提供 8 种 namespace（见第 1 章时间线），容器最常用其中 6 种：

### 各 namespace 隔离了什么

| namespace | 容器里看到什么 | 没有它会怎样 |
|---|---|---|
| **pid** | 只有自己的进程（容器内 PID 1 是入口进程） | 能看到宿主机所有进程，可发信号杀死宿主进程 |
| **net** | 自己的网卡、路由表、iptables、端口空间 | 所有容器共用一张网卡，端口冲突 |
| **mnt** | 自己的挂载点视图（rootfs） | 共用宿主文件系统，能读写宿主文件 |
| **uts** | 自己的 hostname | hostname 冲突 |
| **ipc** | 自己的 System V/POSIX 消息队列 | 共享内存冲突 |
| **user** | 容器内 root（uid 0）映射到宿主一个非特权 uid | 容器 root = 宿主 root（极危险） |

### 怎么进入 namespace：`clone` / `unshare` / `setns`

内核提供三个系统调用来操作 namespace：

- **`clone(2)`**：在创建子进程时同时创建新的 namespace（`CLONE_NEWPID | CLONE_NEWNET | ...`）。runc 创建容器主进程用这个。
- **`unshare(2)`**：让当前进程离开某些共享的 namespace，进入新的。
- **`setns(2)`**：让一个进程加入一个已存在的 namespace（`docker exec` 进容器就用它——把你的 shell 加入目标容器的所有 namespace）。

> **核心心智模型**：namespace 不是"创建一个隔离的环境"，而是"创建一组新的资源视图，然后把进程放进去"。容器进程仍跑在同一个内核上，只是它"看到"的世界被改写了。

### user namespace：容器安全的支柱

`user namespace`（2013 进入内核，最晚成熟的）是容器安全的革命性能力：它允许**容器内的 uid 0（root）映射为宿主机上的一个普通 uid**。这意味着即使容器里的进程拿到了 root 权限，在宿主机看来它也只是个无权限用户——无法影响宿主。

这直接催生了 **rootless 容器**（rootless Docker / rootless Podman / containerd 的 userns 支持）：非 root 用户也能跑容器，且容器逃逸的危害被限制到该用户。这是 8.x 章"运行时安全"的核心。

## 2.3 三大基石之二：cgroups —— 限制"能用多少"

namespace 解决了"看得见什么"，但管不了"用多少资源"。一个被隔离的进程仍可以 `fork bomb` 或吃光内存把宿主 OOM。**cgroups** 补上这一条。

### cgroup v1 vs v2

- **cgroup v1**：每种资源一个层级（cpu 一个、memory 一个……），进程可以挂在不同层级，管理复杂、容易不一致。
- **cgroup v2（2016 起，kernel 4.5）**：**统一层级（unified hierarchy）**——所有资源控制器（controllers）挂在同一棵树，进程的层级关系与资源控制一致，语义更清晰。现代发行版（RHEL 9 / Fedora / Ubuntu 22.04+）默认 cgroup v2 unified 模式。

> containerd/runc 都已支持 cgroup v2（systemd 驱动）。cgroup v2 是 2024 年 OCI Runtime Spec v1.2 强化的重点之一。

### 容器最关心的几个 controller

| controller | 控制什么 | 容器里的体现 |
|---|---|---|
| **cpu** + **cpuacct** | CPU 配额与计量 | `--cpus=2`（限制 2 核）、`--cpu-shares`（相对权重） |
| **memory** | 内存上限 + OOM 控制 | `--memory=4g`（超了触发 OOMKill）、`--memory-swap` |
| **pids** | 进程数上限 | 防止 fork bomb，`--pids-limit=200` |
| **blkio**（v1）/ **io**（v2） | 块设备 IO 带宽 | 限制磁盘读写速率 |
| **devices** | 可访问的设备节点 | 默认禁止访问 `/dev` 下裸设备 |

### CPU 限制的两种语义：CFS quota vs shares

- **`cpu.max`（CFS bandwidth control）**：硬上限。`200000 100000` 表示每 100ms 周期可用 200ms CPU 时间 = 2 核。超了内核**节流（throttle）**该 cgroup。这是 K8s `resources.limits.cpu` 的实现。
- **`cpu.weight`（shares）**：相对权重，只在 CPU 争抢时起作用。这是 K8s `resources.requests.cpu` 的实现（影响调度与争抢时的分配比例）。

> 容器 CPU 限流（throttling）是一个**常见的生产性能陷阱**：当容器周期性变慢，第一个该查的就是 `/sys/fs/cgroup/.../cpu.stat` 里的 `nr_throttled`——AI 推理服务对此尤其敏感（一个 batch 突然变慢就是被 throttle 了）。

### memory 的 OOM 行为

cgroup memory controller 给每个 cgroup 设一个软硬上限：

- **`memory.max`**（硬上限）：超过 → 内核 OOM Killer 杀掉该 cgroup 里内存最大的进程。这是容器被 `OOMKilled` 的根因（`kubectl describe` 里看到的 `OOMKilling`）。
- **`memory.high`**（软上限）：超过 → 内核更激进地回收该 cgroup 的页缓存，但不杀进程。

> 在 K8s 里，Pod 的 `resources.limits.memory` → 容器 cgroup 的 `memory.max`。设错（设太小）→ OOMKill；不设 → 容器能吃光宿主内存，把整个节点拖垮（K8s 节点级别的 OOM 会按 oom_score 乱杀进程，可能杀掉关键系统 Pod）。**内存 limit 是生产里最重要的资源声明之一。**

## 2.4 三大基石之三：overlayfs —— 分层文件系统与"镜像"

容器镜像不是一个大文件，而是**一堆只读层（layer）的集合**。怎么把这些层变成一个可读写的根目录？靠**联合文件系统（union filesystem）**。

### 联合挂载与 copy-on-write

**overlayfs**（Linux 3.18+，是当下默认）的工作原理：

```
┌─────────────────────────────────────────┐
│           merged（统一视图）              │  ← 容器看到的根目录 /
├──────────────┬──────────────────────────┤
│   upperdir   │   （可写层，容器所有修改写这里）│  copy-on-write
├──────────────┴──────────────────────────┤
│   lowerdir N │   ← 镜像最底层（基础镜像，如 debian）│ 只读
│   lowerdir 2 │   ← RUN apt install 的层        │ 只读
│   lowerdir 1 │   ← COPY 源码的层              │ 只读
└─────────────────────────────────────────┘
```

- **lowerdir**：镜像的只读层，从下往上叠加。多个容器共享同一份 lowerdir（节省空间）。
- **upperdir**：容器专属的可写层。容器里**任何写操作**都会触发 **copy-on-write（COW）**——把要修改的文件从 lowerdir 整个复制到 upperdir 再改。
- **merged**：把 lower+upper 联合后的统一视图，挂载到容器根目录。

### COW 的代价：大文件改一行 = 整个文件复制

这是 overlayfs 一个**必须知道**的特性：**修改一个大文件哪怕一个字节，COW 会把整个文件从 lower 复制到 upper**。

- 反例：在镜像里放一个 5GB 的模型文件，启动后写一行 metadata → upperdir 多出 5GB。
- 正解：**大文件、需要写的数据，放 volume（独立目录/云盘），不要写进镜像层**。这也是为什么 AI 镜像里的模型权重常挂载 PVC 或对象存储，而不是 `COPY` 进镜像。

### 分层 = 缓存与去重

分层的真正威力在**复用**：

- 100 个容器都用 `pytorch/pytorch:2.3-cuda` 作基础镜像 → 那 2GB 的基础层在宿主上**只存一份**，100 个容器的 lowerdir 都指向它。
- 你改了 Dockerfile 最后一行 → 前面所有层都命中缓存，只重建最后一层（CI 从 10 分钟降到 30 秒）。

这是镜像"轻量、快速"的工程根基，也是第 9 章"分层与缓存最佳实践"的原理。

## 2.5 镜像（Image）：不可变、内容寻址、可分发

把 namespace + cgroup + overlayfs 串起来，还需要一个"可分发的工件"——这就是**镜像**。OCI Image Spec 定义了镜像的格式（详见第 5 章），核心思想三条：

### 不可变（immutable）

镜像一旦构建，内容永不改变。要"更新"只能构建一个新镜像（新 digest）。这保证了**任何环境拉到的同一个镜像 tag/digest 是字节级一致的**——这是"一次构建到处运行"和"可复现部署"的根基。

> 但注意：**tag 可变，digest 不可变**。`myapp:v2` 这个 tag 可以被重新指向另一个镜像；而 `myapp@sha256:abc123...` 永远指向同一个内容。**生产部署应尽量用 digest 而非 tag 锁定版本**（K8s 默认不这么做，是个常见坑）。

### 内容寻址（content-addressed）

每个层、每个配置都用其内容的 **SHA256 摘要**标识：

- 相同内容的层 → 相同 digest → 自动去重（无论是同一镜像内还是不同镜像间）。
- digest 一致即内容一致 → 可校验完整性、防篡改。

### 可分发（distributable）via registry

镜像通过 **registry**（镜像仓库，遵循 OCI Distribution Spec）分发：`docker pull myreg/myapp:v2` → registry 返回 manifest（这镜像有哪些层）→ 客户端逐层拉取缺失的层（按 digest）。已存在的层不重复拉。Docker Hub、GHCR、 Harbor、各云的 ACR/ECR/GCR 都是 OCI registry。

## 2.6 高层运行时 vs 低层运行时：分层的精髓

这是本主题最重要的概念之一。容器运行时被**人为分成两层**，各自职责清晰：

### 低层运行时（low-level runtime）—— 实现 OCI Runtime Spec

- **职责**：给我一个 `config.json`（描述要哪些 namespace、cgroup、挂载点、要执行的命令），我**真的去 fork/exec 出那个容器进程**。
- **做的事**：调用 `clone(CLONE_NEWPID|CLONE_NEWNET|...)` 创建 namespace、设置 cgroup、挂载 rootfs、`exec` 用户进程。
- **代表实现**：
  - **runc**（Go，OCI 参考实现，最广泛使用）
  - **crun**（C，Red Hat 主导，更轻量、启动更快，CRI-O 默认之一）
  - **youki**（Rust，内存安全方向）
  - **runsc**（gVisor，沙箱运行时）
  - **kata-runtime**（Kata Containers，每个容器一个轻量 VM）
- **不做的事**：不管镜像拉取、不管 CRI、不管卷/网络插件——这些是上层的事。

> 低层运行时**只认 OCI bundle**（一个目录：rootfs + config.json）。它根本不知道"镜像"是什么——镜像的拉取、解包成 rootfs 是高层运行时的工作。

### 高层运行时（high-level runtime）—— 管理镜像与生命周期

- **职责**：管理镜像（拉取、存储、解包成 rootfs）、调用低层运行时创建容器、管理容器生命周期、对接编排系统（通过 CRI）。
- **代表实现**：
  - **containerd**（CNCF 毕业项目，K8s 节点事实默认）
  - **CRI-O**（Red Hat/OpenShift 生态）
- **做的事**：`pull image` → 解析 manifest → 下载 layers → 用 snapshotter 拼成 rootfs → 写 config.json → 调用 `runc create` + `runc start`。

### 一张图看清分层

```
        K8s / Docker CLI / nerdctl
                  │ CRI / 厂商 API
                  ▼
   ┌─────────────────────────────┐
   │  高层运行时 (containerd/CRI-O) │  管：镜像、拉取、snapshot、生命周期、CRI
   └──────────────┬──────────────┘
                  │ OCI Runtime Spec (config.json + rootfs)
                  ▼
   ┌─────────────────────────────┐
   │  低层运行时 (runc/crun/youki) │  做：namespace、cgroup、mount、exec
   └──────────────┬──────────────┘
                  │ clone/setns/cgroup syscalls
                  ▼
            Linux Kernel
```

> **为什么要分两层？** 因为"管理镜像/网络/卷/编排集成"（高层，重，频繁演进）和"创建隔离进程"（低层，薄，必须稳定）的关注点完全不同。把它们解耦，K8s 可以只换高层运行时（containerd↔CRI-O），底层 runc 不动；也可以只换低层（runc↔crun↔kata）做沙箱隔离，高层不动。这种可替换性是 OCI 标准化的核心红利。

## 2.7 OCI 两大规范：钉死"接口"，解放"实现"

OCI（Open Container Initiative）只定义**两个规范**，恰好对应镜像和运行时两个接口：

### Image Specification（image-spec）

定义镜像的内部结构（详见第 5 章）：

- **manifest**：列出这个镜像由哪些层 + 一个 config 组成（按 digest 引用）。
- **config**：镜像的配置——`Env`、`Cmd`、`Entrypoint`、`WorkingDir`、各层的 diffID、要 expose 的端口。
- **layers**：一组压缩的文件系统层（tar.gz / zstd）。
- **manifest list / index**（多架构）：一个索引，列出 amd64/arm64 各自对应的 manifest——这是多架构镜像（`--platform`）的根基。
- **v1.1（2023/2024）新增**：`subject` 字段（支持 referrers——把签名/SBOM/attestation 作为镜像的"附属物"关联）、reference types、**zstd 压缩**支持。

### Runtime Specification（runtime-spec）

定义"如何运行一个 OCI bundle"：

- 输入：一个目录，含 `config.json`（描述进程、rootfs 路径、要创建的 namespaces、cgroup 路径、mounts、capabilities、seccomp 等）和 `rootfs/`。
- 运行时（runc 等）的命令：`create`（创建但不启动，常用于先做绑定再启动）、`start`（启动用户进程）、`kill`、`delete`、`state`、`exec`。
- **v1.2（2024）强化**：cgroup v2、mount extensions（`mount-extended`，更灵活的挂载选项）、idmap mounts（用户态映射挂载，强化 rootless 与安全）。

> 规范的价值不在"规定了什么"，而在"**把运行时和镜像这两个接口钉死**，让上游（镜像构建者、K8s）和下游（runc/crun/kata）可以独立演进、自由组合"。没有 OCI，就没有今天繁荣且可替换的容器生态。

## 2.8 简化心智模型：一页纸理解容器

如果你只能记住一段话，记住这个：

> **容器 = 一个普通进程，被塞进了一组 namespace（改写它的世界视图）+ 一个 cgroup（限制它的资源）+ 一份 overlayfs（从镜像分层拼出的可写根文件系统）。镜像 = 不可变、内容寻址、可分发的分层文件系统归档。运行时 = 高层（containerd，管镜像与生命周期）+ 低层（runc，实际 fork/exec）。OCI = 把"镜像格式"和"运行时接口"标准化，让这一切可互换。**

## 本章小结

本章把容器的核心思想浓缩为**三大内核基石 + 一个镜像抽象 + 一个运行时分层 + 一套标准**：namespace 隔离"看得见什么"、cgroup 限制"能用多少"、overlayfs 实现"分层 + COW 的根文件系统"；这三者共同把一个普通进程"伪装"成独立的运行环境——但请始终记住**容器不是虚拟机，它共享内核，隔离弱于 VM**，这是后续沙箱运行时（gVisor/Kata）存在的理由。镜像用"不可变 + 内容寻址 + 可分发"三个性质，让"环境"变成可像代码一样版本管理、缓存复用的工件。运行时被刻意分为高层（containerd/CRI-O，管镜像与生命周期）与低层（runc/crun/youki，做创建），OCI 用 image-spec 和 runtime-spec 把两个接口钉死，使整个栈可替换、可组合。掌握了这套模型，后面所有章节（架构、工作流程、源码、生产）都是它的展开。

**参考来源**

- [OCI Runtime Specification](https://github.com/opencontainers/runtime-spec)
- [OCI Image Specification](https://github.com/opencontainers/image-spec)
- [Linux `namespaces(7)` man page](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [Linux `cgroups(7)` man page](https://man7.org/linux/man-pages/man7/cgroups.7.html)
- [overlayfs 文档（内核 Documentation）](https://docs.kernel.org/filesystems/overlayfs.html)
- [runc 仓库](https://github.com/opencontainers/runc)
- [containerd 架构文档](https://github.com/containerd/containerd/blob/main/docs/ARCHITECTURE.md)
