# 容器运行时总览

> 一句话理解：**容器运行时是把"镜像"变成"运行中进程"的那一层**——它用 Linux 内核的 namespaces（隔离）、cgroups（限制）、overlayfs（分层文件系统）三件套，加上一个内容寻址、不可变、可分发的**镜像格式**，实现了"一次构建、到处运行"；从 Docker 到 containerd/runc 再到 OCI 标准化，它经历了一场从"一个庞然大物"到"分层解耦、标准可替换"的深刻演进，并最终成为 Kubernetes 之下的"地基"。

## 为什么 AI 平台工程师必须懂容器运行时

Kubernetes 主题讲透了"编排"，但 K8s 自己**不启动容器**——它通过 CRI（Container Runtime Interface）把"运行一个容器"这件事委托给**容器运行时**。当你：

- `kubectl describe pod` 看到 `ContainerCreating` 卡住，根因常常是**镜像拉取失败**或**运行时层错误**；
- 构建一个 8GB 的 PyTorch 镜像却拉不动，需要懂**分层缓存、多阶段构建、distroless**；
- 生产镜像被注入恶意依赖，需要懂**镜像签名（cosign）、SBOM、漏洞扫描（trivy）**；
- 要在 GPU Pod 里隔离不可信推理代码，需要懂**沙箱运行时（gVisor / Kata Containers）**；
- 想让模型镜像秒级拉起，需要懂**惰性拉取（stargz / nydus）**与**镜像分层压缩（zstd）**；

——这些都不是 K8s 的范畴，而是**容器运行时**的范畴。运行时是 K8s 之下、内核之上的那一层，理解它，你才真正"看得到"容器从镜像到进程的完整生命。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释容器的本质：它不是虚拟机，而是**受内核 namespace + cgroup + overlayfs 约束的普通进程**，并说清这三件套各自负责什么。
2. 复述容器运行时的演进史：`chroot → LXC → Docker → runC 捐赠 → OCI 标准化 → containerd/CRI-O 分化 → dockershim 移除`，并解释每一步的设计动机。
3. 区分**高层运行时**（containerd / CRI-O，管镜像、生命周期、CRI）与**低层运行时**（runc / crun / youki，实现 OCI Runtime Spec），画出 `Docker CLI → dockerd → containerd → containerd-shim → runc` 的完整调用栈。
4. 读懂 **OCI 两大规范**：Runtime Specification（容器如何被创建/启动/挂载/cgroup 设置）与 Image Specification（镜像 manifest / config / layers 如何组织、内容寻址如何工作）。
5. 描述 `docker run`（或 `crictl run`）的完整链路：解析镜像引用 → 拉取 manifest → 下载+解压 layers → snapshotter 组成 rootfs → OCI runtime 创建 namespace/cgroup → exec 用户进程 → shim 接管。
6. 看懂 containerd 的核心模块：image store、content store、snapshotter（overlayfs）、containerd-shim、CRI plugin、Transfer Service、NRI，以及 runc/libcontainer 的实现要点。
7. 在生产中做**镜像优化**（多阶段构建、scratch/distroless、分层缓存、多架构 buildx）、**镜像安全**（签名、SBOM、扫描、seccomp/AppArmor/capabilities、rootless）、**沙箱隔离**（gVisor/Kata）、**多架构**（manifest list）。
8. 跑通并扩展本主题的 Mini Demo——一个纯 Python、可在 macOS/CPU 上运行的"容器运行时概念模拟器"（镜像分层 + union/COW + namespace 隔离抽象 + cgroup 计量 + OCI runtime 创建/启动 + 多架构 manifest）。
9. 回答镜像分层、namespace/cgroup、CRI/dockershim、容器与虚拟机本质差异、运行时选型相关的面试题。

## 容器运行时与其他主题的关系

| 主题 | 解决的核心问题 | 与容器运行时的关系 |
|---|---|---|
| [Foundation](/01-foundation/) | Linux 内核、网络、存储 | 容器运行时**直接调用**内核特性：namespaces/cgroups/overlayfs/seccomp/capabilities；Foundation 是它的地基 |
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | 进程调度、内存管理、I/O、网络、cgroup/namespace 内核机制 | 容器运行时讲“怎么用 namespace/cgroup 做容器”，Linux 系统调优讲“这些机制在内核里如何实现、对性能有什么影响” |
| [Kubernetes](/02-cloud-native/kubernetes/) | 声明式编排、调度 | K8s **不启动容器**，通过 CRI 把运行委托给容器运行时（containerd/CRI-O）；运行时是 K8s 之下的执行层 |
| **容器运行时** | 镜像管理 + 容器生命周期 | 本主题，K8s 的地基、所有容器化 AI 服务的执行底座 |
| [vLLM](/04-llmops/vllm/) / [Triton](/04-llmops/triton/) | 推理引擎 | 它们被打成镜像、由运行时拉起；镜像优化直接影响冷启动与扩缩速度 |
| [Ray](/03-ai-platform/ray/) | 分布式 Python 计算 | Ray 的 worker 同样以容器形态在 K8s 上由运行时管理 |
| [AI SRE](/07-ai-sre/) | 可观测、SLO | 运行时指标（containerd metrics、cAdvisor）是容器层可观测的数据源 |
| [安全](/08-security/) | IAM、Secrets、Zero Trust | 运行时的 seccomp/AppArmor/capabilities/rootless/镜像签名是容器安全的核心执行点 |
| [Google](/09-case-study/google/) | 超大规模基础设施 | Google 的容器（lmctfy/Borgulet）是容器技术的先驱，理念直接影响了 OCI/Docker |

## 本章结构

1. [背景](01-background) — 从 `chroot` 到 LXC，Docker 为何引爆，运行时如何从"一个 daemon"演化为"分层解耦 + OCI 标准"，dockershim 移除始末。
2. [核心思想](02-core-ideas) — 容器不是虚拟机；namespaces + cgroups + overlayfs 三件套；不可变、内容寻址的镜像；高层 vs 低层运行时；OCI 两大规范。
3. [架构设计](03-architecture) — Docker/ containerd / runc 三层栈；containerd-shim 的作用；CRI 插件位置；BuildKit 与 registry 的角色。
4. [Runtime 工作流程](04-runtime-workflow) — `docker run`/`crictl runp` 全链路：引用解析 → 拉取 → 解包成 snapshot → OCI runtime create/start → shim 接管。
5. [核心模块](05-core-modules) — image/content store、snapshotter（overlayfs）、containerd-shim、runc/libcontainer、CRI plugin、Transfer Service、NRI、镜像 manifest/config/layers。
6. [源码分析](06-source-analysis) — `opencontainers/runc` 的 libcontainer 与 `create/start` 实现；`containerd/containerd` 仓库结构与关键调用链；`moby/moby` 历史角色。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的"容器运行时概念模拟器"：镜像分层 + union/COW + namespace 抽象 + cgroup 计量 + OCI 创建/启动 + 多架构 manifest。
8. [企业生产实践](08-production-practice) — 镜像优化、镜像安全（签名/SBOM/扫描）、运行时安全（seccomp/AppArmor/capabilities/rootless）、沙箱运行时（gVisor/Kata）、多架构、惰性拉取、registry 运营。
9. [最佳实践](09-best-practices) — Dockerfile 黄金法则、分层与缓存、基础镜像选型、镜像瘦身、运行时配置、CI/CD 集成。
10. [面试题](10-interview-questions) — 初/中/高级面试题。
11. [延伸阅读](11-further-reading) — 官方文档、OCI 规范、源码、论文、生产实践。

## 一句话总结

容器运行时的全部精妙，可以用一句话概括——**"把镜像变成进程"**。它不发明新的隔离技术（Linux 内核早就有 namespace/cgroup），它的贡献在于**标准化与工程化**：用 OCI 规范把"镜像格式"和"运行时行为"钉死，让 Docker/containerd/CRI-O/runc/crun/youki 这些实现可以无缝互换，让 Kubernetes 可以只管编排而不管执行。理解了"namespaces 隔离可见性、cgroups 隔离资源、overlayfs 实现分层"这三个内核原语，以及"高层运行时管生命周期、低层运行时做创建"的分层，你就拥有了从镜像冷启动卡顿一路追到内核 cgroup 的全栈视野。
