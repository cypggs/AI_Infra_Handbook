# 11. 延伸阅读与学习路径

> 一句话理解：本章是容器运行时主题的"出口"——把官方规范、权威文档、源码仓库、经典论文/演讲、生态工具整理成一张可循序的阅读地图，并标出它与本手册其他主题（Kubernetes、vLLM、Triton、AI SRE、安全）的衔接点。

## 11.1 OCI 规范（最权威，必读）

OCI 规范是容器运行时的"宪法"，没有比它更权威的来源：

| 规范 | 读什么 |
|---|---|
| [OCI Runtime Specification](https://github.com/opencontainers/runtime-spec) | 容器如何被创建/启动；config.json 字段；create/start/exec 生命周期；bundle 概念 |
| [OCI Runtime Specification — runtime.md](https://github.com/opencontainers/runtime-spec/blob/main/runtime.md) | runc 各命令的精确语义 |
| [OCI Runtime Specification — config-linux.md](https://github.com/opencontainers/runtime-spec/blob/main/config-linux.md) | Linux 专属：namespaces/cgroups/capabilities/seccomp/sysctl 的 config 字段 |
| [OCI Image Specification](https://github.com/opencontainers/image-spec) | 镜像 manifest/config/layers/index 结构；内容寻址 |
| [OCI Image Specification — manifest.md](https://github.com/opencontainers/image-spec/blob/main/manifest.md) | manifest 与 image-spec v1.1 的 subject/referrers |
| [OCI Distribution Specification](https://github.com/opencontainers/distribution-spec) | registry 的 pull/push API |

**阅读技巧**：spec 不长（每个几百行），但密度极高。建议边读边对照 `runc spec`（生成一份示例 config.json）和 `crane config/manifest`（看真实镜像结构）。

## 11.2 官方文档与权威资料

### containerd

- [containerd 官方文档](https://containerd.io/docs/)
- [containerd ARCHITECTURE.md](https://github.com/containerd/containerd/blob/main/docs/ARCHITECTURE.md) —— 架构权威来源
- [containerd Snapshots](https://github.com/containerd/containerd/blob/main/docs/snapsholders.md)
- [containerd Shim v2](https://github.com/containerd/containerd/blob/main/runtime/v2/README.md)
- [containerd 2.x 迁移与新特性](https://github.com/containerd/containerd/blob/main/RELEASES.md)
- [containerd CRI 插件文档](https://github.com/containerd/containerd/blob/main/docs/cri.md)

### runc / crun / youki

- [runc 仓库与文档](https://github.com/opencontainers/runc)
- [runc SECURITY（安全模型）](https://github.com/opencontainers/runc/blob/main/docs/security.md)
- [crun 仓库](https://github.com/containers/crun)
- [youki（Rust OCI runtime）](https://github.com/containers/youki)

### Docker / BuildKit

- [Docker 官方文档](https://docs.docker.com/)
- [Dockerfile 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [BuildKit 仓库](https://github.com/moby/buildkit) / [buildx 文档](https://docs.docker.com/build/buildx/)
- [moby/moby（Docker Engine 上游）](https://github.com/moby/moby)

### Kubernetes 运行时接口

- [Kubernetes Container Runtimes（CRI）](https://kubernetes.io/zh-cn/docs/setup/production-environment/container-runtimes/)
- [CRI 架构](https://kubernetes.io/zh-cn/docs/concepts/architecture/cri/)
- [dockershim 移除 FAQ](https://kubernetes.io/blog/2022/02/17/dockershim-faq/)
- [CRI API（protobuf）](https://github.com/kubernetes/cri-api)
- [Kubernetes User Namespaces（GA）](https://kubernetes.io/docs/concepts/workloads/pods/user-namespaces/)

### Linux 内核

- [`namespaces(7)` man page](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [`cgroups(7)` man page](https://man7.org/linux/man-pages/man7/cgroups.7.html)
- [`user_namespaces(7)`](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)
- [overlayfs 内核文档](https://docs.kernel.org/filesystems/overlayfs.html)
- [`pivot_root(2)`](https://man7.org/linux/man-pages/man2/pivot_root.2.html) / [`clone(2)`](https://man7.org/linux/man-pages/man2/clone.2.html)

## 11.3 经典论文与演讲（理解设计哲学）

容器技术的内核能力有明确的来源论文/文档，回到源头能理解"为什么这么设计"：

| 资源 | 贡献 |
|---|---|
| [《Resource Containers》（Banga 等，OSDI'99）](https://www.usenix.org/legacy/events/osdi99/full_papers/banga/banga.pdf) | 早期"资源容器"概念，cgroups 思想源头之一 |
| [Google cgroups 原始 patch 讨论](https://lwn.net/Articles/240660/)（LWN，2007） | cgroups 进入内核的设计动机 |
| [《Solaris Zones》（Price & Tucker，USENIX 2004）](https://www.usenix.org/legacy/publications/library/proceedings/lisa04/tech/full_papers/price/price.pdf) | 操作系统级容器的早期工程实践 |
| [《An Analysis of Hardening the Linux Kernel via User Namespace》（学术/工程分析）](https://lwn.net/Articles/543313/) | user namespace 的安全意义 |
| [Liz Rice「Build a container in a few lines of Go」](https://www.youtube.com/watch?v=8fi7uSYlOdc) | 用 ~100 行 Go 从零实现一个迷你容器，绝佳的"容器即系统调用"教学 |
| [Julia Evans「Container zines」](https://jvns.ca/) | 直观图解 namespaces/cgroups/overlayfs |

> **强烈推荐** Liz Rice 的演讲和 Julia Evans 的图解——它们把抽象规范变成"原来就这么几个系统调用"的直观认知，是入门容器运行时最快的路径。

## 11.4 安全与供应链专题

| 资源 | 读什么 |
|---|---|
| [Sigstore / cosign](https://www.sigstore.dev/) | 镜像签名、keyless、Fulcio/Rekor |
| [SLSA Framework](https://slsa.dev/) | 供应链可信度等级、provenance |
| [Syft（SBOM）](https://github.com/anchore/syft) / [Trivy](https://trivy.dev/) / [Grype](https://github.com/anchore/grype) | SBOM 生成与漏洞扫描 |
| [gVisor](https://gvisor.dev/) | 用户态内核架构、runsc |
| [Kata Containers](https://katacontainers.io/) | 轻量 VM 沙箱、硬件隔离 |
| [Kubernetes Pod Security Standards](https://kubernetes.io/zh-cn/docs/concepts/security/pod-security-standards/) | restricted 基线、seccomp/capabilities 配置 |
| [CIS Docker / Kubernetes Benchmark](https://www.cisecurity.org/benchmark/docker) | 安全加固基线 |

## 11.5 性能与冷启动专题

| 资源 | 读什么 |
|---|---|
| [stargz-snapshotter（Lazy Pulling）](https://github.com/containerd/stargz-snapshotter) | estargz 惰性拉取原理与配置 |
| [Nydus（Dragonfly）](https://nydus.dev/) | 内容寻址 + 预取的惰性拉取 |
| [containerd Transfer Service（2.x）](https://github.com/containerd/containerd/blob/main/docs/transfer.md) | 流式镜像传输 |
| [crun 性能对比](https://github.com/containers/crun#performance) | crun vs runc 启动/内存对比 |
| [cgroup v2 与 systemd 驱动](https://systemd.io/CGROUP_DELEGATION/) | K8s 与容器运行时的 cgroup 一致性 |

## 11.6 源码阅读入口

| 入口 | 路径 | 看什么 |
|---|---|---|
| [opencontainers/runc](https://github.com/opencontainers/runc) | `libcontainer/process_linux.go`、`rootfs_linux.go`、`cgroups/` | 容器创建的系统调用实现 |
| [containerd/containerd](https://github.com/containerd/containerd) | `cmd/containerd/`、`core/runtime/`、`plugins/cri/`、`plugins/snapshotter/overlayfs/` | 高层运行时全貌 |
| [moby/buildkit](https://github.com/moby/buildkit) | `cmd/buildctl/`、`frontend/dockerfile/`、`solver/` | 构建、缓存、多阶段并行 |
| [containers/crun](https://github.com/containers/crun) | `src/libcrun/` | C 实现对照（OCI 语言无关） |
| [containers/youki](https://github.com/containers/youki) | `crates/` | Rust 实现对照（内存安全） |
| [containerd/stargz-snapshotter](https://github.com/containerd/stargz-snapshotter) | 惰性拉取实现 |

**源码阅读建议**（第 6 章详述）：
1. 先读 runc（小而精华），跟 `runc create` → `clone` → init 进程内 `pivot_root`+`capset`+seccomp → `exec`。
2. 再读 containerd，跟一次 `PullImage` + `CreateContainer` + `Start`。
3. 对照 crun 看 OCI 的语言无关性。

## 11.7 工具与生态（动手必备）

| 工具 | 用途 |
|---|---|
| **docker / nerdctl** | 开发机构建运行；nerdctl 是 K8s 节点上 Docker 兼容体验 |
| **crictl** | K8s 节点调试（纯 CRI 命令） |
| **ctr** | containerd 原生底层调试 |
| **crane**（go-containerregistry） | registry 操作、查 manifest、export 镜像 |
| **dive** | 镜像分层体积分析 |
| **buildx** | 多阶段/多架构构建 |
| **trivy / syft / grype** | 扫描 / SBOM |
| **cosign** | 签名/校验 |
| **podman / buildah / skopeo** | Red Hat 生态（daemonless、rootless、镜像搬运） |
| **Harbor** | 企业 registry（扫描/签名/复制/配额） |
| **kind / minikube** | 本地起测试集群 |

**动手建议**：本地装 Docker + dive + crane + trivy；按第 7 章 Mini Demo 跑通"镜像分层 + OCI 流程"模拟器；再在 kind 上用 `crictl` 真实复现一次拉镜像、起容器、看 cgroup。

## 11.8 与本手册其他主题的交叉引用

容器运行时是 Kubernetes 之下的地基，与多条主线衔接：

| 主题 | 与容器运行时的关系 | 阅读建议 |
|---|---|---|
| **[Kubernetes](/02-cloud-native/kubernetes/)** | K8s 通过 CRI 调用容器运行时；运行时是 K8s 的执行层 | K8s 第 4 章 Runtime 工作流程与本主题第 4 章互补 |
| [Foundation](/01-foundation/) | namespace/cgroup/overlayfs 都是内核特性 | Foundation 的 Linux/网络/存储是运行时地基 |
| **[vLLM](/04-llmops/vllm/)** / **[Triton](/04-llmops/triton/)** | 推理引擎打成镜像、由运行时拉起 | 镜像优化直接影响它们的冷启动与扩缩 |
| **[Ray](/03-ai-platform/ray/)** | Ray worker 以容器形态在 K8s 上由运行时管理 | KubeRay + containerd |
| **[AI SRE](/07-ai-sre/)** | containerd metrics、cAdvisor 是容器层可观测数据源 | CPU throttle、OOMKill 的监控来自运行时 |
| **[安全](/08-security/)** | 运行时的 seccomp/capabilities/rootless/镜像签名是容器安全执行点 | 本主题第 8 章与安全主题重叠 |
| **[Google](/09-case-study/google/)** | lmctfy/Borgulet 是容器先驱，理念影响 OCI/Docker | 历史/设计哲学 |

## 11.9 推荐学习路径

### 路径 A：AI 应用工程师补运行时（已有 K8s 基础）

1. 本主题第 1–4 章（背景→核心思想→架构→工作流程）—— 建立心智模型。
2. 第 9 章最佳实践 + 第 8 章 8.1/8.6（镜像优化 + 惰性拉取）—— 让你的 AI 镜像又小又快。
3. 跳到 [vLLM](/04-llmops/vllm/) / [Triton](/04-llmops/triton/) 看镜像如何落地。
4. 需要时回查第 10 章面试题、第 8 章安全/沙箱。

### 路径 B：平台/SRE 工程师深入运行时

1. 本主题第 1–6 章（含源码分析）—— 打深基础。
2. OCI Runtime/Image Spec 原文 + runc libcontainer 源码 —— 理解"容器即系统调用"。
3. containerd ARCHITECTURE.md + cri 插件源码 —— 理解 K8s 如何驱动运行时。
4. 第 8 章安全/沙箱 + [安全](/08-security/) 主题 —— 生产加固。
5. stargz/nydus + Transfer Service —— 冷启动优化深入。

### 路径 C：快速入门（只想会用）

1. 本主题 index + 第 2 章（核心思想）+ 第 4 章（工作流程）。
2. 第 9 章 Dockerfile 黄金法则 —— 直接抄进项目。
3. 本地装 Docker，跟着第 7 章 Mini Demo 跑一遍镜像分层与 OCI 流程。

## 本章小结

容器运行时的学习路径以 **OCI 规范**为最高权威（runtime-spec/image-spec/distribution-spec），辅以 containerd/runc 的官方文档与源码；经典论文（Resource Containers、Solaris Zones）和 Liz Rice 的"从零实现容器"演讲帮你把抽象规范变成"原来就这么几个系统调用"的直观认知；生态工具链（docker/nerdctl/crictl/crane/dive/trivy/cosign/Harbor）覆盖了构建、调试、安全、分发的全流程。对 AI 方向的读者，重点是**镜像优化（多阶段/distroless/分层缓存）+ 大镜像冷启动（stargz/nydus）+ 运行时安全（restricted 基线）+ 沙箱（gVisor/Kata 用于不可信代码）**，并顺着本手册的 Kubernetes、vLLM、Triton、安全、AI SRE 主题看运行时如何被上层使用。最重要的是**动手**——本地跑一遍 Mini Demo、用 dive 拆开一个真实镜像、在 kind 上用 crictl 看一次容器创建，远比读十遍文档有效。容器运行时是"看得见的 K8s 地基"，掌握它，你就拥有了从镜像冷启动一路追到内核 cgroup 的全栈视野。

**参考来源**

- [OCI 官网](https://opencontainers.org/)
- [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec) / [Image Spec](https://github.com/opencontainers/image-spec) / [Distribution Spec](https://github.com/opencontainers/distribution-spec)
- [containerd 官网与文档](https://containerd.io/docs/)
- [runc 仓库](https://github.com/opencontainers/runc) / [crun](https://github.com/containers/crun) / [youki](https://github.com/containers/youki)
- [Sigstore](https://www.sigstore.dev/) / [gVisor](https://gvisor.dev/) / [Kata Containers](https://katacontainers.io/)
- [stargz-snapshotter](https://github.com/containerd/stargz-snapshotter) / [Nydus](https://nydus.dev/)
- [Harbor](https://goharbor.io/) / [Trivy](https://trivy.dev/) / [dive](https://github.com/wagoodman/dive) / [crane](https://github.com/google/go-containerregistry)
- [Kubernetes Container Runtimes](https://kubernetes.io/zh-cn/docs/setup/production-environment/container-runtimes/)
- [Liz Rice — Containers from scratch](https://github.com/lizrice/containers-from-scratch)
