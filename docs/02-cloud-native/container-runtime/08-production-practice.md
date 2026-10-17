# 8. 企业生产实践：镜像优化、安全、沙箱与冷启动

> 一句话理解：把容器跑起来只是开始，生产化的真正难点在**镜像优化**（多阶段构建/distroless/分层缓存）、**镜像供应链安全**（签名/SBOM/扫描/可信构建）、**运行时安全**（seccomp/capabilities/rootless/只读根）、**强隔离沙箱**（gVisor/Kata）、**多架构**（buildx）和**冷启动优化**（惰性拉取 stargz/nydus）——尤其对 AI 场景，几十 GB 的模型镜像冷启动慢是弹性扩缩的直接瓶颈。本章给出每条线的工程落地。

## 8.1 镜像优化：让镜像小、快、可缓存

镜像大直接导致：拉取慢（扩缩慢）、磁盘占用高、攻击面大（装了用不到的工具）。优化是基本功。

### 8.1.1 多阶段构建（Multi-stage build）—— 第一优先级

用多阶段构建把"构建环境"和"运行环境"分离，**只把产物拷进最终镜像**：

```dockerfile
# ---- 构建阶段：带完整工具链，体积大 ----
FROM golang:1.22 AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download                  # 依赖层，缓存命中
COPY . .
RUN CGO_ENABLED=0 go build -o app -ldflags="-s -w" ./cmd/app

# ---- 运行阶段：极小 ----
FROM gcr.io/distroless/static-debian12
COPY --from=builder /src/app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

效果：从 `golang`（~900MB）→ distroless static（~2MB + 你的二进制）。**AI 场景同样适用**：用带 CUDA/torch 的镜像构建，但把推理二进制 + 权重处理拷进精简运行镜像。

### 8.1.2 基础镜像选型：distroless / scratch / alpine

| 基础镜像 | 体积 | 内容 | 适用 |
|---|---|---|---|
| `scratch` | 0 | 空（连 shell 都没有） | 静态二进制、最小镜像 |
| `gcr.io/distroless/*` | 2–20MB | 只有运行时（如 `:python3`、`:nodejs`），无 shell/package manager | **生产推荐**，攻击面最小 |
| `alpine` | ~5MB | musl libc + busybox | 体小，但有 musl 兼容坑（Python/C 扩展可能报错） |
| `debian-slim` / `ubuntu` | 20–80MB | glibc，兼容性好 | 兼容性优先 |
| `python:3.x-slim` | ~50MB | 带 Python，无编译器 | Python 应用 |
| `nvidia/cuda` / `pytorch/pytorch` | 2–10GB | CUDA + cuDNN + 框架 | AI（不可避免地大） |

> **AI 特例**：PyTorch/CUDA 基础镜像很大（GB 级），无法像 Go 那样缩到几 MB。策略是：(1) 用 `pytorch/pytorch:2.x-cuda12-cudnn-runtime`（runtime 而非 devel，省掉编译器）；(2) 模型权重**不打进镜像**，挂载 PVC/对象存储，或用 stargz 惰性拉取（见 8.6）。

### 8.1.3 分层缓存：把"变"与"不变"分开

Dockerfile 每条指令一层，**层缓存按指令顺序失效**——一条指令变了，它及之后所有层都重建。所以**把不变的内容（依赖）放前面，常变的内容（源码）放后面**：

```dockerfile
# ✅ 正确：依赖层（pip install）在前，源码层在后
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # 只有 requirements.txt 变了才重建这层
COPY . .                                              # 源码天天变，只重建这一层

# ❌ 错误：COPY . . 在前，任何源码改动都让 pip install 层失效
COPY . .
RUN pip install -r requirements.txt
```

对 AI 镜像同理：`COPY requirements.txt` + `pip install` 在前，`COPY model/ code/` 在后。

### 8.1.4 其他瘦身手段

- **`.dockerignore`**：排除 `node_modules/`、`.git/`、测试数据、本地权重——防止把它们 COPY 进构建上下文（构建上下文会被整体发给 daemon）。
- **`--no-cache-dir`**（pip）/ **`--no-install-recommends`**（apt）：不留包管理器缓存。
- **`-ldflags="-s -w"`**（Go）：去掉调试符号。
- **`apt-get clean && rm -rf /var/lib/apt/lists/*`**：同一层内清理 apt 缓存（注意必须**同一 RUN**，否则上一层已固化）。
- **合并 RUN**：多个 `RUN` 合成一个，减少层数（但牺牲缓存粒度，权衡）。
- **zstd 压缩**（image-spec v1.1 支持）：比 gzip 压缩率相近、解压快，containerd/buildkit 已支持。

### 8.1.5 量化指标

用 **dive**（镜像分层分析工具）或 `docker history` 检查每层体积。生产 AI 镜像目标：基础（CUDA/torch）+ 代码 + 依赖 < 8GB；不把模型打进镜像。

## 8.2 镜像供应链安全：签名、SBOM、扫描、可信构建

镜像供应链攻击（恶意依赖、被篡改的 base image、registry 投毒）是真实威胁。完整防护链：

### 8.2.1 镜像签名：Sigstore / cosign

**Sigstore** 是镜像签名的开源标准（CNCF），核心组件 **cosign** 给镜像签名。机制（image-spec v1.1 的 subject/referrers）：

- 签名作为**独立的 OCI 附属物**（不修改被签镜像），通过 `subject` 指向被签镜像的 digest；
- registry 的 **referrers API** 让客户端"发现"某镜像的所有附属物（签名/SBOM）；
- 部署时**策略校验**（K8s 用 **Kyverno** / **OPA Gatekeeper** / **Sigstore Policy Controller**）——只允许带有效签名的镜像部署。

```bash
# 给镜像签名（keyless，用 OIDC 如 GitHub Actions）
cosign sign --yes myreg/app:v1@sha256:abc123...

# 验证签名
cosign verify myreg/app:v1 --certificate-identity https://github.com/myorg/... --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

**keyless 签名**（Sigstore Fulcio + Rekor）是趋势——不长期保管私钥，签名时用 OIDC 身份（如 GitHub Actions 的 token）签发短期证书，签名记录存入 **Rekor**（透明日志，可审计）。这与 Let's Encrypt 用短期证书替代长期私钥的理念一致。

### 8.2.2 SBOM（软件物料清单）

**SBOM** 记录镜像里所有依赖（包名、版本、来源），是漏洞追踪与合规的基础：

- 生成工具：**syft**（CNCF）、**trivy**（自带 SBOM）、**docker buildx** 的 `--sbom=true`。
- 格式：**SPDX**（ISO 标准）、**CycloneDX**（OWASP）。
- SBOM 同样作为 image-spec v1.1 的附属物挂载到镜像，可被发现、可追踪。

```bash
syft myreg/app:v1 -o cyclonedx-json > sbom.json
cosign attach sbom --sbom sbom.json myreg/app:v1
```

### 8.2.3 漏洞扫描

- **trivy**（Aqua）：最流行，扫 OS 包 + 语言依赖 + IaC + 私有 registry。
- **grype**（Anchore，与 syft 配套）。
- **Harbor**（带内置 Trivy，CI 流水线里自动扫）。

策略：CI 里 **构建后即扫**，**High/Critical CVE 阻断发布**。生产里用 **Daily scan**（新 CVE 持续暴露，今天没漏洞的镜像明天可能有）。

### 8.2.4 可信构建（SLSA / provenance）

**SLSA（Supply-chain Levels for Software Artifacts）** 评估构建过程的可信度。**provenance attestation** 记录"这个镜像在哪、用什么源码、什么构建参数构建的"——用 cosign attestation 附到镜像上。部署时可校验"只允许从特定源码仓库 + 特定分支构建的镜像"。

> 这套（签名 + SBOM + 扫描 + provenance）是 2024–2026 年镜像供应链安全的**事实标准栈**。AI 镜像因体量大、依赖复杂（CUDA/torch/pip），更需要这套——一个被注入恶意 pip 包的推理镜像能窃取线上推理流量。

### 8.2.5 digest pinning：锁定不可变内容

```dockerfile
# ✅ 锁定 digest（内容不可变）
FROM python@sha256:abc123... AS base

# ⚠️ tag 可变，有漂移风险
FROM python:3.12-slim AS base
```

CI 里用 **Renovate / Dependabot** 自动把 tag 升级并重算 digest，兼顾"锁定"与"可升级"。

### 8.2.6 校验下沉：容器级的 image verifier

containerd 2.0 引入 **image verifier 插件**：在 **pull 阶段**就按策略校验镜像签名（如 cosign 公钥、OIDC issuer），校验失败直接拒绝拉取。这与 K8s 准入控制（Kyverno/Gatekeeper）互补——前者管"节点上根本拉不下来"，后者管"API 层拒绝创建"——两层都做才闭环。

## 8.3 运行时安全：权限收窄四件套 + 版本治理

镜像安全管"进去什么"，运行时安全管"跑起来能干什么"。四条核心配置，外加一条 2025 年用血的教训换来的治理原则：

### 8.3.1 非 root 运行

容器默认以 root（uid 0）运行——即使有 user namespace，容器内 root 仍是危险默认。**生产应始终非 root**：

```dockerfile
USER 10001:10001        # Dockerfile 里指定
```

或运行时强制：`docker run --user 10001:10001` / K8s `securityContext.runAsUser: 10001` + `runAsNonRoot: true`（设 `runAsNonRoot` 会让 kubelet 在检测到 root 时拒绝启动）。

### 8.3.2 只读根文件系统

```yaml
# K8s
securityContext:
  readOnlyRootFilesystem: true     # 根文件系统只读，攻击者无法写入后门
  # 需要写的目录（如 /tmp、缓存）单独挂 emptyDir/卷
```

```bash
docker run --read-only --tmpfs /tmp alpine
```

### 8.3.3 capabilities drop + no-new-privileges

Linux capabilities 把 root 权限细分成几十项（`CAP_NET_BIND_SERVICE`、`CAP_SYS_ADMIN`…）。容器默认 drop 大部分但仍保留若干。**生产应显式 drop ALL，只按需 add**：

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false      # no_new_privs，防止 setuid 提权
  capabilities:
    drop: [ALL]
    add: [NET_BIND_SERVICE]            # 只加必需的
```

### 8.3.4 seccomp / AppArmor / SELinux

- **seccomp**：过滤系统调用。容器默认 seccomp profile 已禁用几十个危险系统调用（如 `keyctl`、`mount`）。可自定义更严 profile。
- **AppArmor**（Debian/Ubuntu）/ **SELinux**（RHEL/CentOS）：强制访问控制，限制进程能访问的文件/能力。K8s 通过 `securityContext.seccompProfile` / `appArmorProfile` 配置。

> K8s 1.25+ 起 `securityContext.seccompProfile` 默认 `RuntimeDefault`，节点 Pod Security Admission 的 **restricted** 级别要求上述四件套全开。**生产 Pod 应满足 `restricted` 级别**——这是行业基线。

### 8.3.5 版本治理：低层运行时是全栈最薄的安全板

2025 年 10 月，runc 在一周内被披露了三个容器逃逸 CVE（**CVE-2025-31133、CVE-2025-52565、CVE-2025-52881**）——低层运行时直接握着 namespace/cgroup/mount 的创建权，一旦出洞就是"容器内 root → 宿主 root"。运营要求：

- **runc/containerd/NVIDIA Container Toolkit 版本纳入漏洞响应 SLA**：高危逃逸 CVE 应在补丁发布后数日内滚动升级节点（2025 年 NVIDIA Container Toolkit 也修复了 CVE-2025-23266/23267 等 CDI 模式漏洞）；
- **节点镜像/运行时可重建**：把 containerd、runc、操作系统打进不可变节点镜像（image-based Linux + ignition/cloud-init），CVE 补丁 = 换节点镜像，而不是 SSH 上去 yum upgrade；
- **用 RuntimeClass 混用运行时**：对安全敏感负载切 crun（历史 CVE 仅约 4 个）或沙箱运行时，普通负载保持 runc 兼容。

### 8.3.6 user namespace：Pod 级 rootless 正式可用

容器内 root（uid 0）可映射为宿主机无特权用户——逃逸也无宿主权限。此前 K8s 里这条路受内核/运行时能力限制，**2026 年已 GA**：K8s v1.36 起 `pod.spec.hostUsers: false` 稳定可用，要求内核 ≥6.3（idmap mounts）、containerd ≥2.0（或 CRI-O ≥1.25）、runc ≥1.2（或 crun ≥1.9）。对每个 Pod 分配独立的宿主 UID/GID 映射区间，是"多租户集群里跑不可信工作负载"最划算的加固手段，与沙箱运行时（8.4）可以叠加。

## 8.4 沙箱运行时：gVisor、Kata 与 AI Agent 沙箱

容器共享内核，隔离弱于 VM。对**不可信代码**（多租户里的用户代码、跑用户 prompt 生成代码的 Agent），需要更强的隔离——**沙箱运行时**提供"容器体验 + VM 级隔离"。2025–2026 年这个领域的最大变化，是 **AI Agent 代码执行沙箱**成为主要增长场景，以及 **gVisor/Kata 先后补上 GPU 这块短板**。

### 8.4.1 gVisor（runsc）—— 用户态内核

Google 的 **gVisor** 实现了一个**用户态内核（Sentry）**：容器进程的系统调用**不直接进入宿主内核**，而是被 gVisor 拦截、用 Go 重新实现后再安全地转发给宿主内核。

```
传统容器：     容器进程 ──syscall──▶ Linux Kernel（共享，内核漏洞=逃逸）
gVisor：       容器进程 ──syscall──▶ gVisor Sentry（用户态，Go 实现的 syscall 处理）──有限接口──▶ Kernel
```

- **隔离强度**：远高于普通容器（容器只通过 gVisor 暴露的有限接口接触内核，大部分内核攻击面被屏蔽）。
- **代价**：性能损耗（系统调用多了一层，CPU/IO 密集型有 10–50% 损耗）。
- **运行时**：`runsc`（OCI Runtime Spec 实现），通过 `containerd-shim-runsc-v1` 接入 containerd/K8s；不需要 KVM，是"低成本沙箱"的默认选项。
- **GPU（2024–2025 的重要更新）**：gVisor 通过 **`nvproxy`** 提供了生产可用的 NVIDIA GPU 支持（拦截 CUDA ioctl，已覆盖 A100/H100 等；Google 与 Groq 合作把 gVisor 用于 LLM 推理沙箱，GPU 推理平台 Modal 也用它跑 ML 沙箱）。注意它只放行 ioctl 白名单，**不提供超出 NVIDIA 驱动配置之外的硬件级隔离**。
- **生产背书**：Google 全家桶（GKE Sandbox、Cloud Run、App Engine）默认使用。

### 8.4.2 Kata Containers —— 每容器一个轻量 VM

**Kata Containers** 给每个容器/Pod 启动一个**轻量级虚拟机**（基于 KVM/Firecracker/Cloud Hypervisor），容器进程跑在 VM 内——硬件级隔离，但用 containerd/CRI 接口，体验同普通容器。

```
Kata：    containerd ──shim-kata──▶ 轻量 VM（QEMU/Firecracker/Cloud Hypervisor）──▶ 容器进程（VM 内）
```

- **隔离强度**：最强（VM 级，hypervisor 硬件隔离）。
- **代价**：启动慢于普通容器（热启动百毫秒级、冷启动秒级）、每 Pod 多一份 VM 内存开销（约数百 MB 量级）、I/O 有额外开销；需要独立节点池/RuntimeClass 运营（GKE `kata-qemu-nvidia-gpu`、AKS `kata-vm-isolation` 等托管方案已可用）。
- **GPU**：支持 **GPU 直通**（每 Pod 独占整卡或 MIG 切片），是"多租户不可信推理代码要碰 GPU"时的首选——这也是它与 Firecracker 的关键差异（Firecracker 无 PCIe/GPU 直通，基本被排除在 GPU 场景外）。
- **适用**：最高隔离需求（金融、跑极度不可信代码、多租户 GPU 推理）。

### 8.4.3 AI Agent 沙箱：2025 年的新主战场

LLM Agent 需要执行模型生成的代码/工具调用，"不可信代码执行"从边缘需求变成主流场景，催生了专门实践：

- **k8s-sigs/agent-sandbox**（KubeCon NA 2025 发布）把 **gVisor 与 Kata 明确定义为 AI Agent 负载的两大标准隔离后端**，用 K8s 原生方式供给沙箱；
- **热池（warm pool）/预创建沙箱**：Agent 交互要求亚秒级响应，等"冷启动一个沙箱"不可接受——平台普遍预创建一批已就绪的沙箱（预拉镜像、预热文件缓存），用完即焚；
- **隔离深度与风险匹配**：不少团队（如 METR 的公开评估）实测后选择"留在 gVisor"——没有测出与 Kata 的隔离差距，而成本和复杂度显著更低。选型原则：**先 gVisor，实测不够再 Kata**，而不是默认上 VM。

### 选型对比

| 维度 | runc（普通） | gVisor (runsc) | Kata Containers |
|---|---|---|---|
| 隔离机制 | namespace+cgroup（共享内核） | 用户态内核（拦截 syscall） | 轻量 VM（硬件隔离） |
| 隔离强度 | 弱～中 | 中～强 | 强（≈VM） |
| 性能损耗 | 无 | 中（CPU/IO 密集 10–50%） | 启动慢、I/O/内存开销 |
| 启动速度 | 毫秒 | 毫秒～秒 | 热启动百毫秒、冷启动秒级 |
| GPU 支持 | 原生（经 CDI，见 8.8） | nvproxy（ioctl 白名单，无硬件级隔离） | GPU 直通（每 Pod 独占） |
| 适用 | 信任的工作负载 | 多租户/不可信代码/Agent 沙箱 | 极不可信/合规/多租户 GPU |
| OCI 兼容 | 是 | 是 | 是 |

> AI 场景的落地建议：**可信推理服务**用 runc + CDI 注入 GPU（性能无损，见 8.8）；**不可信用户代码/Agent 工具执行**用 gVisor（CPU 代码沙箱）或 Kata（需要 VM 级边界或 GPU 独占时）；同时可叠加 8.3.6 的 Pod 级 user namespace 作为纵深防御。Firecracker 在纯 CPU 微沙箱（Serverless、CI 隔离）依然流行，但因无 GPU 直通，在 GPU 推理沙箱的选型中基本让位给 Kata/gVisor。

## 8.5 多架构镜像（multi-arch）

混架构集群（x86 训练 + ARM 推理，如 AWS Graviton、Ampere）要求镜像支持多架构。**BuildKit/buildx** 一次构建多架构 manifest list：

```bash
docker buildx create --use --name multi-builder
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myreg/app:v1 \
  --push .
```

产物是一个 image index（manifest list），客户端按 `--platform` 自动选对应子 manifest。Dockerfile 用**架构变量**处理差异：

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.22 AS builder
ARG TARGETOS TARGETARCH
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o app ./cmd/app

FROM --platform=$TARGETPLATFORM alpine
COPY --from=builder /src/app /app
```

> AI 镜像多架构更复杂（CUDA 在 ARM 上是不同的包），常分架构单独构建再合并 manifest。但对推理服务（纯 Python + torch wheel），多架构已较成熟。

## 8.6 冷启动优化：惰性拉取（Lazy Pulling）

传统镜像必须**整镜像下载完才能启动**——对几十 GB 的 AI 模型镜像，冷启动动辄分钟级，严重拖慢弹性扩缩。**惰性拉取**让镜像不下载完即可启动，首次访问文件时才从 registry 拉那部分。2025 年起这条赛道形成三条互补的技术路线：

### stargz / estargz

Google 的 **stargz**（及其增强版 estargz）把镜像层**重新组织**成"可随机访问的索引"格式，containerd 的 **stargz-snapshotter** 配合，运行时按需从 registry 读文件。需要构建时重打包，但应用代码零改动。

### SOCI（AWS）—— 不改镜像的旁路索引

**SOCI（Seekable OCI）** 的思路不同：对**未经修改的原生 gzip 镜像**生成一个"可跳转索引"（ztoc，记录文件到层内字节范围的映射），索引本身作为 **OCI 1.1 附属物**（referrers API）存进 registry——镜像 digest、层、签名全部不变，registry 和构建工具也无需改动。AWS 论文报告：1.3GB 镜像冷启动拉取提速 **7.4 倍**（20s → 约 2.8s）、2.5GB 提速 9.3 倍，拉取阶段只取约 **11%** 的数据；访问密度低于约 80% 时惰性加载优于全量并行拉取。生产上已用于 **EKS 优化 AMI 与 ECS Fargate**（2025 年 Prime Day 期间 Fargate 单日启动 1840 万个任务）。

### nydus（Dragonfly，阿里）

**nydus** 是内容寻址 + 本地缓存 + 预取（预热关键文件）的方案，镜像需转为 RAFS 格式。对"模型权重 + 代码"混合镜像，能优先拉代码（启动快）、模型按需/后台拉。

### zstd:chunked：让普通镜像也能惰性加载

`zstd:chunked` 压缩格式（containers/storage 生态，BuildKit/Podman 已支持）把 zstd 层切成独立解压的 chunk，使**普通 zstd 镜像无需转换为特殊格式**即可按 chunk 惰性加载与去重拉取——是"惰性拉取"与"标准镜像格式"趋于合流的标志。

### 效果

- 镜像 10GB，但启动只需要 100MB 代码 → 冷启动从"下 10GB"变成"下 100MB + 后台流式拉模型"。
- 对**AI 推理弹性扩缩**（突发流量扩容）是关键优化。

> containerd 2.x 的 Transfer Service 原生支持流式 + 惰性拉取 snapshotter，是落地 stargz/nydus/SOCI 的标准路径。

## 8.7 镜像仓库运营：Harbor

企业自建 registry 通常选 **Harbor**（CNCF 毕业）：

- **漏洞扫描**：内置 Trivy，push 时自动扫，可设"High CVE 阻止 pull"。
- **签名**：集成 cosign，镜像签名策略。
- **复制（replication）**：跨 region/registry 自动同步镜像（多云、灾备）。
- **配额与多租户**：项目（project）级配额、RBAC。
- **GC**：定期清理无引用 blob（Harbor 内置 GC 任务）。
- **机器人账号**：CI 拉推用的 service account。

运营要点：(1) 设保留策略（保留最近 N 个 tag，旧版本 GC）；(2) 启用签名校验 + 漏洞扫描门禁；(3) 大镜像考虑 P2P 分发（Dragonfly/Kraken）减轻 registry 压力。

## 8.8 GPU 容器的设备注入：从 nvidia runtime 到 CDI

AI 平台每天"容器里跑 GPU"的实现方式，在 2025 年发生了一次静默换代。理解这条演进，你就理解了 CDI（Container Device Interface）为什么重要。

### 老路：预置 runtime + 环境变量

早期做法是 NVIDIA Container Toolkit 在 containerd 配置里注册一个专用 **`nvidia` runtime**（`runc` 的包装）：Pod 声明 `runtimeClassName: nvidia`（或 env `NVIDIA_VISIBLE_DEVICES`）才走这条路。问题是它**污染了全局 runtime 配置**——每个节点多一个 runtime 分支，与 K8s Device Plugin 的交互也绕。

### 新路：CDI 标准化注入（当前默认）

**CDI 是 containerd/CRI-O 内置的通用"设备注入"标准**（类比 CNI 之于网络）：设备信息写成一个 JSON 规格文件（设备节点、驱动库、挂载、环境变量），运行时按 CDI 设备名原样注入容器——**不需要专用 runtime，默认 runc 路径就能跑 GPU**。

- **NVIDIA GPU Operator v25.10（2025）起，CDI 成为默认注入方式**；`nvidia-ctk cdi generate` 可自动生成 CDI 规格；Container Toolkit v1.18+ 支持按配置自动生成与 distroless 单镜像打包；
- 升级兼容：存量 `runtimeClassName: nvidia` 的 Pod 继续可用，但新部署应走默认 runc + CDI；
- CDI 注入的不只是 GPU——MIG 配置设备、IMEX 通道、甚至**按 GPU 的 CUDA 显存限额**（`NVIDIA_GPU_MEMORY_REQUEST/LIMIT`，需 R615+ 驱动）都可以通过 CDI 规格表达；
- **安全提醒**：2025 年 7 月 NVIDIA 修复了 Container Toolkit/Device Plugin 的 **CVE-2025-23266/23267**（影响 CDI 模式），用 CDI 的团队同样要把 toolkit 版本纳入漏洞 SLA（见 8.3.5）。

> 对 AI 平台工程师的实操结论：**新集群直接上 containerd 2.x + GPU Operator ≥ v25.10（CDI 默认）**，Pod 只声明 `resources.limits."nvidia.com/gpu"` 与镜像，不再配置 `runtimeClassName`；CDI 让"GPU 注入"第一次成为与网络（CNI）、存储（CSI）同级别的标准插件接口。

## 8.9 AI 场景特化的容器运行时实践

把上述综合到 AI 平台：

1. **镜像分层**：`nvidia/cuda:runtime`（共享基础层）→ `pytorch runtime` → `app+依赖`（变动层）→ **模型权重不打进镜像**（挂 PVC/对象存储 或 nydus/SOCI 惰性拉取）。
2. **冷启动**：大模型镜像用 nydus/SOCI，代码与权重分离，秒级拉起。
3. **GPU 注入**：containerd 2.x + GPU Operator ≥ v25.10，走 **CDI 默认注入**（不再配 `runtimeClassName: nvidia`），Pod 只声明 `nvidia.com/gpu`。
4. **沙箱**：可信推理用 runc；跑用户生成代码的 Agent 沙箱用 gVisor（CPU，可叠加 Pod 级 user namespace）；多租户不可信 GPU 推理用 Kata GPU 直通。
5. **安全**：所有镜像 cosign 签名 + SBOM + Trivy 扫描门禁；生产 Pod 满足 Pod Security `restricted`；runc/containerd/toolkit 版本纳入漏洞 SLA。
6. **多架构**：x86 训练集群 + ARM 推理集群共用多架构 manifest。

## 本章小结

生产化的容器运行时实践围绕**让镜像小/快/安全**、**让隔离足够强**与**让设备注入足够标准**三条主线：镜像优化靠**多阶段构建 + distroless/scratch 基础镜像 + 分层缓存 + .dockerignore + zstd**；镜像供应链安全靠 **cosign 签名（keyless）+ SBOM（syft）+ 漏洞扫描（trivy）+ SLSA provenance + digest pinning + 容器级 image verifier** 的完整栈；运行时安全靠**非 root + 只读根 + capabilities drop ALL + seccomp/AppArmor** 四件套（对应 K8s Pod Security `restricted` 级别），加上 2025 年教训换来的**版本治理**（runc 逃逸 CVE、NVIDIA toolkit 漏洞都要求运行时补丁进 SLA）和 **Pod 级 user namespace**（K8s v1.36 GA）这道新防线；强隔离靠沙箱运行时——**gVisor（用户态内核，nvproxy 补上 GPU）**与**Kata Containers（每 Pod 一个轻量 VM，GPU 直通）**，2025 年起的主战场是 AI Agent 代码执行沙箱（agent-sandbox 项目 + 热池）；GPU 注入已从专用 nvidia runtime 换代为 **CDI 标准化注入**（GPU Operator v25.10 起默认）；多架构靠 **buildx** 一次构多架构 manifest；冷启动靠**惰性拉取**——重打包（stargz/estargz）、旁路索引（**SOCI**，不改镜像、提速 7 倍以上）、内容寻址（**nydus**）三条路线，加上 **zstd:chunked** 让标准镜像也能按 chunk 惰性加载。把这些落地，你交付的就不是"能跑的容器"，而是"生产级、安全、快"的容器化平台。

**参考来源**

- [Sigstore / cosign](https://www.sigstore.dev/) / [cosign GitHub](https://github.com/sigstore/cosign)
- [Syft（SBOM）](https://github.com/anchore/syft) / [Trivy](https://github.com/aquasecurity/trivy) / [Grype](https://github.com/anchore/grype)
- [SLSA Framework](https://slsa.dev/)
- [gVisor](https://gvisor.dev/)（GPU 支持见 [gVisor GPU 文档](https://gvisor.dev/docs/user_guide/gpu/)）/ [Kata Containers](https://katacontainers.io/)
- [k8s-sigs/agent-sandbox（AI Agent 沙箱）](https://github.com/kubernetes-sigs/agent-sandbox)
- [Kubernetes User Namespaces（v1.36 GA）](https://kubernetes.io/docs/concepts/workloads/pods/user-namespaces/)
- [NVIDIA Container Toolkit（Release Notes）](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/release-notes.html) / [GPU Operator CDI 支持](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/cdi.html) / [NVIDIA Container Toolkit 安全公告（2025-07）](https://nvidia.custhelp.com/app/answers/detail/a_id/5659/)
- [stargz-snapshotter](https://github.com/containerd/stargz-snapshotter) / [Nydus](https://nydus.dev/) / [SOCI（awslabs）](https://github.com/awslabs/soci-snapshotter)
- [Harbor](https://goharbor.io/)
- [Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/)
- [Distroless 镜像](https://github.com/GoogleContainerTools/distroless)
- [Kubernetes Pod Security Standards](https://kubernetes.io/zh-cn/docs/concepts/security/pod-security-standards/)
- [dive（镜像分层分析）](https://github.com/wagoodman/dive)
