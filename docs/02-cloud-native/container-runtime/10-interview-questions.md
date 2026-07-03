# 10. 面试题：容器运行时初/中/高级

> 一句话理解：面试里考容器运行时，本质是考你**是否真懂"容器即受约束的进程"**、**是否理解分层与标准化的工程价值**、**能否在生产故障前定位到运行时层**。本章按初/中/高级组织题目，每题给"答题要点"而非标准答案——引导你讲清背后的原理与权衡。

## 10.1 初级（概念与基础）

### Q1：容器和虚拟机有什么本质区别？

**答题要点**：
- 隔离粒度：VM 是硬件级（每个跑一个客户机内核）；容器是进程级（共享宿主内核）。
- 资源/启动开销：VM 几 GB 内存、秒～分钟启动；容器几 MB、毫秒启动。
- 隔离强度：VM 强（hypervisor）；容器弱（共享内核，内核漏洞=逃逸，这是 gVisor/Kata 存在的理由）。
- 一句话：VM 虚拟硬件，容器虚拟操作系统视图。容器是宿主上受 namespace/cgroup/overlayfs 约束的**普通进程**。
- 可验证：`docker run -d alpine sleep 1000` 后宿主 `ps aux | grep sleep` 能看到该进程。

### Q2：Linux namespace 有哪些？容器用了哪些？

**答题要点**：
- 列举：pid、net、mnt、uts、ipc、user、cgroup（、time）。
- 容器常用 6 种（pid/net/mnt/uts/ipc/user）。
- 各隔离对象（pid→进程号、net→网络栈、mnt→挂载点、uts→hostname、ipc→消息队列、user→uid 映射）。
- user namespace 的意义：容器内 root 映射到宿主非特权 uid，rootless 容器的根基。
- 操作系统调用：clone（创建时建 namespace）、unshare、setns（exec 进容器用）。

### Q3：cgroup 是做什么的？v1 和 v2 有什么区别？

**答题要点**：
- 作用：对进程组限制与计量 CPU/内存/IO/PID/设备等资源。
- v1：每资源一个层级，进程可挂多层级，管理复杂、易不一致。
- v2（kernel 4.5+）：统一层级，所有 controller 挂同一棵树，语义清晰；现代发行版默认 v2 unified。
- 容器最关心：cpu（CFS quota/shares）、memory（OOM）、pids（fork bomb 防护）。
- `memory.max` 对应 K8s `resources.limits.memory`，超了 OOMKill；`cpu.max` 对应 `limits.cpu`，超了 throttle。

### Q4：什么是 OCI？它定义了哪两个规范？

**答题要点**：
- OCI（Open Container Initiative，2015 Linux 基金会）制定开放容器标准，避免被单一公司锁定。
- **Runtime Specification**：如何运行一个 OCI bundle（config.json + rootfs），定义 runc 的 create/start/exec 等命令与行为。
- **Image Specification**：镜像格式（manifest/config/layers/index），内容寻址、分层。
- 价值：把"镜像格式"和"运行时接口"钉死，让 Docker/containerd/CRI-O/runc/crun/youki 可互换组合。

### Q5：`docker run` 后，宿主机上能看到那个进程吗？

**答题要点**：
- 能。容器进程就是宿主上的普通进程（只是被塞进 namespace/cgroup）。
- 宿主 `ps` 看到它的真实 PID（不是容器内的 PID 1）。
- 这是"容器即进程"的最直接证明——容器不是虚拟机，没有独立的内核调度实体。

### Q6：镜像为什么是分层的？分层有什么好处？

**答题要点**：
- 每条 Dockerfile 指令一层；联合文件系统（overlayfs）把只读层 + 可写层联合挂载。
- 好处：(1) 复用——多个容器共享基础层，磁盘只存一份；(2) 缓存——Dockerfile 改一行只重建该层及之后；(3) 增量传输——pull 时只拉缺失的层。
- 内容寻址（digest 去重）：相同层跨镜像也共享。

## 10.2 中级（架构与工作流程）

### Q7：Docker、containerd、runc 三者是什么关系？

**答题要点**：
- 分层调用：`docker` CLI → `dockerd`（Docker Engine，可选层）→ `containerd`（高层运行时）→ `containerd-shim` → `runc`（低层运行时）→ 内核。
- 历史演进：2015 Docker 把运行时核心剥离成 containerd/runc 捐赠社区；dockerd 沦为在 containerd 之上加 Docker 体验的薄层。
- K8s 节点上通常只有 containerd（无 dockerd），调试用 `crictl`/`nerdctl`。

### Q8：高层运行时和低层运行时分别负责什么？为什么要分两层？

**答题要点**：
- 低层（runc/crun/youki）：实现 OCI Runtime Spec，给一个 bundle（config.json+rootfs）就 fork/exec 出容器进程，只做 namespace/cgroup/mount。
- 高层（containerd/CRI-O）：管镜像（拉取/存储/解包成 rootfs）、容器生命周期、对接编排（CRI）。
- 为什么分两层：关注点分离——"管理镜像/网络/编排"（重、演进快）vs"创建隔离进程"（薄、需稳定）。分层让上层可换（containerd↔CRI-O）或下层可换（runc↔crun↔kata 做沙箱）而不影响其他层。

### Q9：containerd-shim 的作用是什么？为什么需要它？

**答题要点**：
- 问题：早期容器进程直接由 dockerd fork，dockerd 重启会杀掉所有容器；runc 创建完容器就退出，容器父进程归属成问题。
- shim 是每个容器一个的"代理父进程"：runc create 完退出后，shim 接管容器进程的父进程角色。
- 三大好处：(1) 解耦守护进程——containerd 重启容器不受影响；(2) 接管 runc 退出后的 reap/信号/日志/exec；(3) 故障隔离——单容器 shim 崩溃不影响其他。
- 不同 runtime 有不同 shim（runc-v2 / runsc-v1 / kata-v2）。

### Q10：解释 `docker run` 的完整流程（从命令到进程启动）。

**答题要点**（按第 4 章时序）：
1. CLI → dockerd（REST）→ containerd（gRPC）。
2. Image Service 检查本地镜像；缺则 Transfer Service 从 registry 拉 manifest → 逐层拉 blobs 进 Content Store。
3. Snapshotter 解包层 → 构建快照树 → 准备 rootfs。
4. containerd fork shim。
5. shim 调 `runc create`：clone namespace + 设 cgroup + 挂 rootfs（pivot_root）+ 收窄权限，建进程但不 exec。
6. shim 调 `runc start`：exec 用户进程 → Running。runc 退出，shim 接管。

### Q11：overlayfs 是怎么工作的？什么是 COW？COW 有什么代价？

**答题要点**：
- overlayfs 联合挂载：lowerdir（只读镜像层）+ upperdir（容器可写层）+ workdir → merged 视图作为容器根。
- COW（copy-on-write）：容器修改文件时，把文件从 lowerdir 整个复制到 upperdir 再改，lowerdir 不变。
- 代价：**改一个大文件哪怕 1 字节，整个文件被复制**（5GB 模型改一行 metadata → upperdir 多 5GB）。
- 正解：大文件/需写的数据放 volume，不要进镜像层。

### Q12：镜像的 manifest、config、layers、manifest list 分别是什么？

**答题要点**：
- **manifest**：单架构清单，列 config + 各层（按压缩后 digest）。
- **config**：镜像配置（Env/Entrypoint/Cmd/User/ExposedPorts + 各层未压缩 diff_id + history）。
- **layers**：压缩的文件系统增量（tar.gz/zstd）。
- **manifest list / index**：多架构索引，列各架构对应的子 manifest。
- config 里 diff_ids（未压缩）vs manifest 里 layers digest（压缩）的区别：解压后用 diff_id 校验完整性。
- v1.1 新增 subject/referrers：签名/SBOM 作为附属物可发现挂载。

### Q13：K8s v1.24 移除 dockershim 意味着什么？Docker 构建的镜像还能在 K8s 上跑吗？

**答题要点**：
- 移除的是 kubelet 里对接 dockerd 的 dockershim 适配层，不是禁止 Docker。
- K8s 节点默认运行时变为 containerd（或 CRI-O），通过 CRI 直接调用，无需 dockerd。
- **Docker 构建的镜像（OCI 兼容）完全能在 K8s 上跑**——这是社区反复澄清却仍被误解的一点。移除的是运行时适配层，不是镜像。
- 实际影响：节点上调试用 `crictl`/`nerdctl` 而非 `docker`。

### Q14：一个 Pod 里的容器为什么能通过 localhost 互通？

**答题要点**：
- CRI 里 Pod 是"沙箱"：先 `RunPodSandbox` 创建一个 **pause 容器**，它持有 Pod 的 net/ipc namespace。
- 业务容器 `CreateContainer` 时被配置为**加入 pause 的 net/ipc namespace**。
- 因此同 Pod 容器共享网络栈、共享 loopback，localhost 互通、端口不冲突。
- pause 容器"占位"namespace：业务容器重启，Pod IP 不变。

## 10.3 高级（生产、安全、调优、源码）

### Q15：容器被 OOMKilled 是什么原因？怎么排查？

**答题要点**：
- 根因：容器内存超过 cgroup `memory.max`（= K8s `limits.memory`），内核 OOM Killer 杀掉该 cgroup 内存最大的进程。
- 排查：`kubectl describe pod` 看 `Last State: Terminated, Reason: OOMKilled`；看容器内存用量 vs limit。
- 常见：(1) limit 设太小；(2) 内存泄漏；(3) 模型/batch 过大（AI 推理 batch 太大爆显存→进程内存也涨）；(4) JVM/Python GC 不到位。
- 解法：调大 limit、修泄漏、控制 batch、用内存敏感的 GC 参数。
- 区分"容器 OOMKill"（cgroup 限制）vs"节点 OOM"（整机内存耗尽，按 oom_score 乱杀）。

### Q16：容器 CPU throttle 是什么？为什么 AI 推理服务会被它拖慢？

**答题要点**：
- CFS bandwidth control：`cpu.max` 设每周期可用 CPU 时间，超了内核节流（throttle）该 cgroup。
- 现象：容器周期性变慢（throttle 期间停 CPU）。
- AI 影响：推理 batch 处理时间敏感，被 throttle 后 batch 延迟飙升、排队。
- 排查：`/sys/fs/cgroup/.../cpu.stat` 看 `nr_throttled`/`throttled_usec`。
- 解法：(1) limits.cpu 设够大或用 `cpu.max` 更宽；(2) 注意 K8s `limits.cpu` 是硬限，requests 只是调度权重——很多人误以为设了 requests 就够，实际 throttle 由 limits 决定。

### Q17：怎么把镜像体积从 8GB 降到 500MB？多阶段构建具体怎么做？

**答题要点**：
- 多阶段：构建阶段（带编译器/CUDA devel）→ 运行阶段（runtime，只拷产物）。
- 基础镜像：runtime 而非 devel；distroless/alpine/debian-slim。
- 分层缓存：依赖层在前，源码在后。
- `.dockerignore`：排除本地权重/数据/缓存。
- 同 RUN 清理：`apt clean && rm -rf /var/lib/apt/lists/*`。
- `-ldflags="-s -w"`（Go 去 debug 符号）。
- 量化：用 `dive` 找出最大的层。
- AI 特例：CUDA/torch 基础层无法缩，但把模型权重移出镜像（挂载）能省几个 GB。

### Q18：镜像供应链安全怎么保证？讲讲 cosign 签名和 SBOM。

**答题要点**：
- 签名（cosign/Sigstore）：签名作为 image-spec v1.1 subject 附属物，不修改原镜像；keyless 用 OIDC（GitHub Actions）签发短期证书，记录进 Rekor 透明日志。
- SBOM（syft）：记录镜像所有依赖（SPDX/CycloneDX），同样作为附属物，用于追踪漏洞。
- 扫描（trivy）：构建后扫 CVE，High/Critical 阻断发布；生产做 daily scan（新 CVE 持续暴露）。
- 可信构建（SLSA/provenance）：cosign attestation 记录构建来源，部署时校验"只允许特定源码仓库构建的镜像"。
- 部署校验：K8s 用 Kyverno/Gatekeeper/Sigstore Policy Controller 拒绝未签名/未授权镜像。
- digest pinning：用 `image@sha256:...` 锁定内容，防 tag 漂移。

### Q19：gVisor 和 Kata Containers 各自的隔离机制和适用场景？

**答题要点**：
- gVisor（runsc）：用户态内核（Sentry），拦截容器 syscall 用 Go 重新实现后安全转发——隔离强于普通容器（屏蔽大部分内核攻击面），性能损耗 10–50%（CPU/IO 密集），适用多租户/不可信代码。不支持 GPU 直通。
- Kata：每个 Pod 一个轻量 VM（KVM/Firecracker/Cloud Hypervisor），容器跑 VM 内——硬件级隔离（≈VM），启动秒级、内存开销大，适用极不可信/合规。
- 共同点：都实现 OCI Runtime Spec，通过对应 shim 接入 containerd/K8s，上层无感切换。
- GPU 场景：gVisor 不支持，Kata 支持但复杂——所以 GPU 推理通常用 runc + 网络隔离，不可信代码沙箱用 gVisor（CPU）。

### Q20：runc 创建容器的核心系统调用有哪些？pivot_root 和 chroot 有什么区别？

**答题要点**：
- clone（CLONE_NEWPID|CLONE_NEWNET|...）创建 namespace；setns（exec 进容器）；cgroupfs 写入设资源；capset 收窄权限；seccomp BPF 过滤 syscall。
- pivot_root vs chroot：chroot 只改进程的 `/` 视图，进程仍能访问原文件系统（不安全）；pivot_root 在 mount namespace 里把根**整体换掉**、旧根卸载，配合 mount namespace 真正隔离。容器用 pivot_root。
- runc "re-exec self as init"：通过 `/proc/self/exe init` 重新执行自己，在新 namespace 里完成初始化再 exec 用户命令。

### Q21：惰性拉取（stargz/nydus）解决什么问题？原理是什么？

**答题要点**：
- 问题：传统镜像必须整镜像下载完才能启动，大镜像（几十 GB 模型镜像）冷启动分钟级，拖慢弹性扩缩。
- 原理：把镜像层重组为"可随机访问/内容寻址"格式，containerd 的 stargz/nydus snapshotter 让运行时按需从 registry 读文件——不必下载完即启动，首次访问文件才拉那部分。
- nydus 支持预取（优先拉代码启动、模型后台流式拉）。
- 对 AI：模型权重不打进镜像 + nydus = 秒级拉起几十 GB 镜像。
- 落地：containerd 2.x Transfer Service 原生支持流式 + 惰性 snapshotter。

### Q22：生产里如何防止"镜像 tag 漂移"导致两次部署拉到不同内容？

**答题要点**：
- 问题：tag（如 `v1.4`）可被重新指向另一个镜像，两次 `image:v1.4` 拉到不同内容。
- 解法：(1) digest pinning——部署清单用 `image@sha256:...`（内容寻址，不可变）；(2) 部署流程主动把 tag 解析成 digest 再下发；(3) cosign 签名 + 部署校验只允许签名的镜像；(4) 禁用 `latest`，用语义版本 + Git SHA 双标签。

### Q23：rootless 容器是什么？为什么它更安全？

**答题要点**：
- rootless：非 root 用户也能跑容器（rootless Docker / Podman / containerd userns）。
- 基础：user namespace——容器内 uid 0（root）映射到宿主一个非特权 uid。
- 安全意义：即使容器逃逸，宿主看来只是个普通用户，无法影响系统/其他容器。
- 代价：部分功能受限（端口 <1024 需 sysctl、某些 mount 不可、网络需 slirp/pasta）。
- 趋势：rootless 是运行时安全的方向，Podman 默认 rootless，containerd/K8s 的 user namespace 支持在完善（K8s 1.30+ GA 的 user namespace 支持）。

### Q24：设计一个 AI 推理服务的镜像与运行时方案，兼顾冷启动、安全、GPU。

**答题要点**（综合题）：
- 镜像分层：`nvidia/cuda:runtime`（共享）→ `pytorch runtime` → app+依赖（变动层）。
- 模型权重不打进镜像：挂 PVC/对象存储 或 nydus 惰性拉取。
- 多阶段构建 + distroless 运行层；代码与依赖分层缓存。
- 运行时安全：非 root、只读根、drop ALL、seccomp（Pod Security restricted）。
- GPU：GPU Operator + containerd runtimeClass 注入设备；resources 声明 `nvidia.com/gpu`。
- 版本：语义版本 + SHA + digest；cosign 签名 + Trivy 扫描 + SBOM 门禁。
- 冷启动：nydus/stargz 惰性拉取 + 副本预热（HPA 扩容时提前 pull）。
- 沙箱：可信推理用 runc；不可信用户代码（Agent 代码沙箱）用 gVisor（CPU）。
