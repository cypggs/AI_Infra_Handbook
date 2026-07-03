# 9. 最佳实践：Dockerfile、分层、运行时与 CI/CD

> 一句话理解：本章把第 8 章的"为什么"浓缩成"怎么做"——一份生产级 Dockerfile 的黄金法则、分层缓存的工程套路、基础镜像与运行时配置的选型清单、镜像版本管理策略、与 CI/CD 的集成模式。每条都对应一个真实踩坑，可以直接抄进团队规范。

## 9.1 Dockerfile 黄金法则（按优先级）

### 法则 1：多阶段构建是默认，不是优化

任何"带构建步骤"的镜像（编译型语言尤其）都该多阶段。构建阶段带工具链，运行阶段极简。

```dockerfile
# ✅ 永远多阶段
FROM node:20 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

### 法则 2：依赖层在前，源码层在后

把"变"与"不变"按缓存友好排序——依赖（requirements.txt / package.json / go.mod）先 COPY 先安装，源码后 COPY。

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # 不变层
COPY . .                                              # 常变层
```

### 法则 3：一个 RUN 合并 + 同层清理

包管理器安装与缓存清理必须在**同一个 RUN**（否则上一层已固化，清理无效）：

```dockerfile
# ✅ 同层安装 + 清理
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ❌ 分开，缓存留在上一层
RUN apt-get update && apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*
```

### 法则 4：用 `.dockerignore`

构建上下文（`docker build` 的最后一个参数，通常是 `.`）会被**整体发给 daemon**。不 `.dockerignore` 的话，`node_modules/`、`.git/`、本地权重、测试数据全进了上下文——慢、占空间、泄露。最小 `.dockerignore`：

```
.git
.gitignore
node_modules
__pycache__
*.pyc
.venv
.env*
*.md
tests/
.DS_Store
# AI：本地权重不要进上下文
*.bin
*.safetensors
*.ckpt
models/
data/
```

### 法则 5：明确声明 `ENTRYPOINT` 与 `CMD`

- `ENTRYPOINT`：容器的"固定命令"（如 `python app.py`），不易被 `docker run` 参数覆盖（除非 `--entrypoint`）。
- `CMD`：默认参数，易被 `docker run` 末尾参数覆盖。
- 推荐用 **exec form**（JSON 数组），不用 shell form——shell form 会让命令成为 `/bin/sh -c` 的子进程，**收不到 SIGTERM**（`docker stop` / `kubectl delete` 的优雅停止失效）。

```dockerfile
# ✅ exec form，PID 1 是你的进程，能收信号优雅退出
ENTRYPOINT ["python", "app.py"]

# ❌ shell form，PID 1 是 /bin/sh，信号被吞
ENTRYPOINT python app.py
```

### 法则 6：非 root + 固定 UID

```dockerfile
RUN groupadd -r app && useradd -r -g app -u 10001 app
USER 10001:10001
```

固定 UID（而非 `USER app` 名字）便于挂载卷时对齐宿主权限。

### 法则 7：声明 `HEALTHCHECK`

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

K8s 通常用 `livenessProbe`/`readinessProbe` 替代，但单 Docker/非 K8s 场景 HEALTHCHECK 仍必要。

## 9.2 分层缓存进阶

### 本地缓存 vs 远程缓存

- **本地缓存**：同机构建，层缓存复用（默认）。
- **远程缓存**（`--cache-from`/`--cache-to`）：CI 跨机器复用层缓存。BuildKit 把缓存推到 registry（作为特殊镜像），下次构建从 registry 拉。

```bash
docker buildx build \
  --cache-from type=registry,ref=myreg/app:cache \
  --cache-to type=registry,ref=myreg/app:cache,mode=max \
  -t myreg/app:v1 .
```

### `mode=max` vs `mode=min`

- `mode=min`（默认）：只缓存最终阶段的层。
- `mode=max`：缓存**所有多阶段**的中间层——对多阶段构建的复用价值更大。

### BuildKit 的并行

BuildKit 会**分析 Dockerfile 的依赖图，并行构建无依赖的 stage**。多阶段里互不依赖的阶段会并行跑——这是把"串行多阶段"变成"并行"的关键，CI 提速明显。

## 9.3 基础镜像与运行时配置选型清单

### 基础镜像决策树

```
静态二进制（Go/Rust）          → scratch / distroless/static
解释型语言（Python/Node）       → distroless/python3 / distroless/nodejs（生产）
                                  或官方 *-slim（开发/兼容性）
需要 shell/包管理器调试          → alpine（体小）或 debian-slim（兼容）
需要 glibc 兼容（C 扩展/某些库） → debian-slim（避免 alpine musl 坑）
AI（CUDA/torch）                → pytorch/pytorch:*-runtime 或 nvidia/cuda:*-runtime
```

### 运行时安全配置（生产基线）

| 配置 | 值 | K8s securityContext |
|---|---|---|
| 运行用户 | 非 root，固定 UID | `runAsNonRoot: true`, `runAsUser: 10001` |
| 根文件系统 | 只读 | `readOnlyRootFilesystem: true` |
| 提权 | 禁止 | `allowPrivilegeEscalation: false` |
| capabilities | drop ALL，按需 add | `capabilities.drop: [ALL]` |
| seccomp | RuntimeDefault | `seccompProfile: {type: RuntimeDefault}` |

这套 = Pod Security **restricted** 级别，是生产基线。

### 资源声明（必填）

```yaml
resources:
  requests: { cpu: 500m, memory: 2Gi }    # 调度依据，必填
  limits:   { cpu: "2",  memory: 4Gi }     # cgroup 上限，必填
```

> **永远声明 requests 与 limits**。不声明 requests → 调度器不知道放哪、QoS 降级；不声明 limits → 容器能吃光节点内存导致整机 OOM。AI 场景 GPU 用 `nvidia.com/gpu`（整数，整卡独占）或 MIG/MPS 共享。

## 9.4 镜像版本管理

### Tag 策略

- **`latest` 是反模式**：不可追溯、有漂移、回滚困难。生产禁用 `latest`。
- **语义化版本**（`v1.4.2`）+ **Git SHA**（`v1.4.2-3f8a1b2`）双标签：前者人读、后者机器唯一。
- **digest 锁定**：部署清单里用 `image@sha256:...` 而非 `image:v1.4.2`，确保 K8s 拉到的是构建时那个内容（防 tag 漂移）。

### 保留与清理

- registry 保留策略：保留最近 N 个 tag + 所有生产 tag；旧版本 GC。
- Harbor / 各云 registry 都支持"保留规则 + 定期 GC"。
- 注意：**正在被 K8s 使用的镜像不能 GC**——GC 前检查引用。

## 9.5 CI/CD 集成模式

### 标准 CI 流水线（构建 → 安全 → 推送）

```yaml
# 伪 pipeline
jobs:
  build:
    steps:
      - checkout
      - docker buildx build --platform linux/amd64,linux/arm64 \
          --cache-from type=registry,ref=app:cache \
          -t app:${SHA} -t app:v1.4.2 .
      - dive app:${SHA}                          # 体积/分层检查
      - trivy image --exit-code 1 --severity HIGH,CRITICAL app:${SHA}   # CVE 门禁
      - syft app:${SHA} -o cyclonedx-json > sbom.json
      - cosign sign --yes app:${SHA}@${DIGEST}   # keyless 签名
      - cosign attach sbom --sbom sbom.json app:${SHA}@${DIGEST}
      - docker push app:${SHA}
```

### 部署侧校验

- K8s 用 **Kyverno / OPA Gatekeeper / Sigstore Policy Controller**：拒绝未签名 / 来自非授权 registry / 不满足 restricted 的镜像。
- 配合 **ArgoCD/Flux（GitOps）**：镜像 digest 进 Git，部署即 Git 状态收敛。

## 9.6 镜像调试技巧

| 需求 | 方法 |
|---|---|
| 看每层体积 | `dive nginx:1.27` 或 `docker history nginx:1.27` |
| 进 distroless（无 shell）的容器调试 | `docker run --entrypoint sh debug:tag`，或用 `kubectl debug` 附加 debug container |
| 看容器内进程 | `docker top` / `crictl inspect` |
| 看容器 cgroup | `cat /sys/fs/cgroup/.../cpu.stat`（throttle）、`memory.current` |
| 查镜像 manifest/config | `docker buildx imagetools inspect nginx:1.27` / `crane config nginx:1.27` |
| 不启动容器，只看镜像文件系统 | `crane export nginx:1.27 - \| tar -tvf -` |

## 9.7 反模式清单（生产禁用）

| 反模式 | 问题 | 正解 |
|---|---|---|
| 用 `latest` tag 部署 | 不可追溯、漂移、难回滚 | 语义版本 + SHA + digest 锁定 |
| 把密钥 `COPY` 进镜像 | 镜像泄露=密钥泄露 | 构建用 BuildKit secret，运行用 K8s Secret |
| root 运行 | 提权逃逸风险 | 非 root 固定 UID |
| shell form ENTRYPOINT | 收不到 SIGTERM，无法优雅停止 | exec form |
| 把模型权重 COPY 进镜像 | 镜像几十 GB、冷启动慢 | 权重挂 PVC/对象存储或 stargz 惰性拉取 |
| 不声明 resources | 调度瞎放、QoS 降级、OOM 节点 | requests + limits 必填 |
| 每条指令一个 RUN | 层数爆炸、缓存碎片 | 合并相关指令 |
| `apt-get install` 不清理 | 缓存留在镜像、变大 | 同 RUN 内 `rm -rf /var/lib/apt/lists/*` |
| 单架构构建 | 跨架构集群拉不到镜像 | buildx 多架构 |
| 不签名不扫描 | 供应链攻击面 | cosign + trivy + SBOM 门禁 |

## 9.8 一份"达标"的生产 Python AI 服务 Dockerfile

把上述法则综合：

```dockerfile
# syntax=docker/dockerfile:1.7
FROM --platform=$TARGETPLATFORM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN groupadd -r app && useradd -r -g app -u 10001 -m -d /home/app app

FROM base AS builder
WORKDIR /install
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

FROM base AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=10001:10001 ./app ./app
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "-m", "app.server"]
# 模型权重不打进镜像，运行时从 PVC/对象存储挂载
```

## 本章小结

最佳实践是把原理变成肌肉记忆：Dockerfile 的七条黄金法则（多阶段默认、依赖层在前、同 RUN 合并清理、`.dockerignore`、exec form ENTRYPOINT、非 root 固定 UID、HEALTHCHECK）；分层缓存的远程缓存（`--cache-from/to` + `mode=max`）与 BuildKit 并行多阶段；基础镜像按决策树选（静态→scratch/distroless、解释型→distroless、AI→pytorch runtime）；运行时配置满足 Pod Security restricted 基线（非 root + 只读根 + drop ALL + seccomp）；资源 requests/limits 必填；版本管理用语义版本 + SHA + digest 锁定、禁用 latest；CI/CD 集成构建→体积检查→CVE 扫描门禁→SBOM→cosign 签名→推送的标准流水线，部署侧用 Kyverno/Gatekeeper 校验签名。把这些固化进团队规范与 CI 模板，每个镜像都自然达到"小、快、安全、可追溯"的生产标准。

**参考来源**

- [Dockerfile 最佳实践（官方）](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [BuildKit 远程缓存](https://docs.docker.com/build/cache/backends/)
- [Distroless 镜像](https://github.com/GoogleContainerTools/distroless)
- [Trivy 扫描](https://trivy.dev/) / [Syft SBOM](https://github.com/anchore/syft)
- [Sigstore / cosign](https://www.sigstore.dev/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/zh-cn/docs/concepts/security/pod-security-standards/)
- [dive（镜像分析）](https://github.com/wagoodman/dive) / [crane（registry 工具）](https://github.com/google/go-containerregistry)
- [Kyverno 策略引擎](https://kyverno.io/)
