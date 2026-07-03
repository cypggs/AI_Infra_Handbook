# 1. 背景：从手写 YAML 到 K8s 包管理

> 一句话理解：本章回答"Helm 为什么存在"——`kubectl apply -f` 在小型 demo 够用，但一旦要管理"多环境、多版本、可回滚、可复用"的整套应用清单，就会陷入 YAML 复制地狱；Helm 把"一整套 K8s 清单"提升为"带参数、带版本、带依赖的软件包（Chart）"，是 K8s 生态事实标准的包管理器。

## 1.1 前提：什么是"一个 K8s 应用"

先对齐一个朴素事实：在 Kubernetes 里，**一个应用通常不是"一个 YAML 文件"，而是"一打 YAML 文件"**。以一个生产级 GPU 推理服务为例，你至少需要：

| 对象 | 干什么 |
|---|---|
| `Deployment` | 管理推理 Pod 副本、滚动升级 |
| `Service` | 集群内稳定的虚拟 IP + 负载均衡 |
| `ConfigMap` | 模型路径、批处理参数、generation 配置 |
| `Secret` | HF token / API key / 数据库密码 |
| `HorizontalPodAutoscaler` | 按延迟/吞吐自动扩缩 |
| `PodDisruptionBudget` | 滚动/节点维护时保最小可用副本 |
| `ServiceMonitor` | 让 Prometheus 抓指标 |
| `NetworkPolicy` | 限制谁能访问推理服务 |
| `Ingress` / `HTTPRoute` | 对外域名 + TLS |
| `ServiceAccount` + `RoleBinding` | RBAC，让 Pod 能拉 Secret |

这些对象**互相引用**（Service 选 Deployment 的 Pod、Ingress 指向 Service、ServiceMonitor 选 Service 的 label、HPA 作用在 Deployment 上），名字、label、selector、端口、域名必须在它们之间保持一致。这正是"包"的本质：**一组有内在引用关系、必须整体安装/升级/卸载的资源**。

## 1.2 裸 YAML 的四宗罪

如果你直接 `kubectl apply -f inference-service/`，会撞上四类问题：

### 罪一：环境差异靠"复制 + 改"

dev / staging / prod 三套环境的副本数、镜像 tag、资源、域名、对外端口都不一样。裸 YAML 的做法通常是**维护三份几乎一样的目录**：

```
manifests/
├── dev/
│   ├── deployment.yaml      # replicas: 1, image: vllm:dev, domain: dev.example.com
│   └── service.yaml
├── staging/
│   ├── deployment.yaml      # replicas: 2, image: vllm:rc,  domain: staging.example.com
│   └── service.yaml
└── prod/
    ├── deployment.yaml      # replicas: 8, image: vllm:v1.4.2, domain: example.com
    └── service.yaml
```

问题：**90% 内容重复，一处改三处同步**。改一个探针路径要在三个目录里各改一遍，漏改就是事故。"DRY（Don't Repeat Yourself）"原则在裸 YAML 下根本无法遵守。

### 罪二：升级即"覆盖"，没有版本，没有回滚

`kubectl apply` 用的是**声明式 last-applied-configuration**：它把"你这次 apply 的"和"集群里现在的"做 diff，apply 上去。这算"升级"，但：

- **没有版本号**：你不知道"当前线上跑的是哪个版本的清单"。
- **没有历史**：apply 之后，"上一个版本长什么样"只存在于你脑子里或 git 历史里，K8s 不记录。
- **回滚靠人肉**：出问题想回滚，要 `git checkout` 到上一个 commit 再 apply，或者从备份翻出旧 YAML。StatefulSet/Deployment 有 `kubectl rollout undo`，但它只管"那一个 workload 的 PodTemplate 版本"，**不管你 apply 的 ConfigMap/Service/Ingress 这些周边对象**。

一句话：裸 apply 没有把"一次发布"当成一个**事务性的、带版本的整体**。

### 罪三：依赖靠"手动按顺序 apply"

装一个 cert-manager，它依赖：先装一堆 CRD（CustomResourceDefinition），再装命名空间、Deployment、Service、RBAC（ServiceAccount/ClusterRole/ClusterRoleBinding）、Webhook 配置。顺序错了（比如 CRD 还没 apply 就 apply Issuer 实例）会报错。裸做法是写一个 `install.sh`：

```bash
kubectl apply -f https://.../cert-manager.crds.yaml
kubectl apply -f https://.../cert-manager.yaml
sleep 10   # 等 webhook ready
kubectl apply -f issuer.yaml
```

脆弱、不可重复、不可声明版本、升级靠删了重装。一个中等规模集群上要装十几个这样的组件，这就是运维噩梦。

### 罪四：复用靠"复制粘贴 + 全局替换"

团队 A 写好了一套"GPT 推理服务"的 YAML，团队 B 想复用。裸做法：`cp -r gpt-service llama-service`，然后 `sed -i 's/gpt/llama/g'`。结果：复制出来的副本和原版彻底分叉，原版修了一个探针 bug，B 团队永远收不到。**没有"模板 + 参数 = 实例"的抽象，就没有真正的复用**。

## 1.3 Helm 的回答：把应用当"软件包"

Helm（"舵"，呼应 Kubernetes 的航海主题）的核心思路是借鉴传统操作系统的包管理器（apt/yum/brew）：

| 传统包管理器 | 干什么 | Helm 对应 |
|---|---|---|
| 软件包（.deb/.rpm） | 一个软件的完整文件 + 元数据 | **Chart**（`.tgz`，含模板 + 默认值 + Chart.yaml 元数据） |
| 包仓库 | 存放/索引软件包 | **Repository**（HTTP server，含 index.yaml）或 OCI registry |
| 安装实例 | 系统上装了一份该软件 | **Release**（某个 chart 在某个 namespace 的一次安装实例） |
| 包版本 | `nginx 1.27` | **Chart 版本**（`Chart.yaml` 的 `version`） |
| 软件版本升级 / 回滚 | `apt upgrade` / 包管理器记录的旧版本 | **Revision**（每次 install/upgrade 都 +1，可 `rollback`） |
| 配置文件 / 环境变量 | 装好后改配置 | **values**（`values.yaml` + `-f` 覆盖 + `--set`） |

把"K8s 应用"提升为"Chart"后，四宗罪一次性解决：

- **环境差异**：一份模板 + 多份 `values-dev.yaml`/`values-prod.yaml`，靠参数区分，模板不重复。
- **版本/回滚**：每次 upgrade 是一个 Revision，`helm rollback myapp 3` 一键回到第 3 版。
- **依赖**：`Chart.yaml` 里声明依赖（`dependencies`），Helm 自动按拓扑顺序安装；Chart 仓库统一版本。
- **复用**：团队共享一个 Chart，各环境只填不同 values。

## 1.4 Helm 的历史：v1 → v2（Tiller）→ v3（无 Tiller）

理解 Helm v3 为什么长这样，必须知道它的前两代。

### Helm v1（2016）与 Classic 模式

最早 Helm（由 Deis 团队，后捐给 CNCF）只有"Classic"概念：Chart 是静态 YAML 的集合（**无模板**），靠 `values.toml` 里的变量做简单替换。能力弱，很快被下面的 v2 取代。

### Helm v2（2016–2019）：模板引擎 + Tiller

v2 引入了两个至今仍是核心的东西：

1. **Go template + Sprig 函数库**：Chart 里是带 <code v-pre>{{ }}</code> 的模板，渲染时填入 values。这是现代 Helm 的基础。
2. **Tiller（舵柄）**：一个**运行在集群内**的服务端组件（一个 Deployment），Helm CLI（客户端）把 Chart 发给 Tiller，**由 Tiller 去调 kube-apiserver** 安装。

Tiller 的设计动机是"让 CI/CD 等无集群管理员权限的系统也能通过 Tiller 部署"。但它带来了**严重的安全问题**：

- Tiller 默认以 **`cluster-admin`** 权限运行（`system:serviceaccount:kube-system:default`），集群内一个高权限后门。
- Tiller **不做鉴权**——任何能连到 Tiller gRPC 端口的人都能以 cluster-admin 身份操作整个集群。
- 多租户环境下，A 团队的 CI 能通过 Tiller 改 B 团队的资源。

这是 v2 最大的痛点。CNCF 社区花了几年也难以彻底解决，最终在 v3 里**直接删掉了 Tiller**。

### Helm v3（2019-11 至今）：客户端渲染，无 Tiller

v3 是一次重大重写，核心变化：

| 维度 | v2（有 Tiller） | v3（无 Tiller） |
|---|---|---|
| 渲染在哪 | 集群内 Tiller 渲染 + apply | **客户端（CLI）渲染**，再用自己的 kube-apiserver 调用（复用 kubeconfig 权限） |
| 鉴权 | Tiller 绕过 K8s RBAC | **直接用调用者的 kubeconfig 权限**，受 RBAC 约束（你有多少权限，Helm 就能做多少） |
| Release 存哪 | 集群内 `kube-system` 的 ConfigMap（v2） | **所在 namespace 的 Secret**（v3，v3.0 仍是 ConfigMap，3.1+ 默认 Secret） |
| Release 作用域 | 全集群（`kube-system`） | **namespace 内**（`helm install` 默认带 namespace，release 名在 namespace 内唯一） |
| CRD 安装 | 不区分 | CRD 单独处理（`crd-install` hook → `templates/crds/` 约定），且**升级时 Helm 不动已存在的 CRD** |
| 三方合并 | 升级用二方（old chart + new chart） | **三方合并**（old chart + old values + new chart+values，见第 3、4 章） |

> **一句话记住 v3 的本质**：Helm v3 不再是一个"集群里的服务"，而只是一个**客户端工具**——它读 Chart、用 values 渲染出 YAML，然后用你的 kubeconfig 把这些 YAML `apply` 到 apiserver。它没有自己的特权，也不常驻集群。这也意味着：**Helm 做的所有事，`kubectl apply` 原则上都能做，Helm 只是把"渲染 + 版本化记录"自动化了**。

v3 之后 Helm 进入稳定演进期，没有 v4 的计划。近年的重要增量（在本主题对应章节详述）：OCI registry 支持（Chart 当 OCI 制品，`helm install oci://...`，2022 GA）、post-renderer、Chart Signing、Library Chart、Lookup 函数、`helm install --take-ownership`。

## 1.5 Helm vs Kustomize：模板 vs 叠加

K8s 配置管理还有另一个事实标准：**Kustomize**（Google 出品，已内置进 `kubectl`）。它与 Helm 是两种不同哲学：

| 维度 | Helm（模板派） | Kustomize（叠加派） |
|---|---|---|
| 核心思想 | **模板 + 变量渲染**（<code v-pre>{{ .Values.x }}</code>） | **无模板的 overlay 叠加**（base YAML + patch） |
| 学习曲线 | 要学 Go template + Sprig 函数 | 几乎不用学语法，只声明"base + 哪些 patch" |
| 抽象方式 | `values.yaml` 参数化 | `kustomization.yaml` 声明 base + patches + namePrefix + images |
| 输出 | 渲染后清单可看 `helm template` | 渲染后清单可看 `kubectl kustomize` / `build` |
| 版本/回滚 | 有 Release/Revision（强项） | 无原生版本（要靠 git + ArgoCD/Flux 的历史） |
| 依赖/子组件 | Chart 依赖、Subchart | 较弱（靠 `resources:` 引用，无原生依赖解析） |
| 生态分发 | Chart 仓库/OCI，海量现成 Chart | 无"包仓库"概念，更"本地化" |
| 内置 | 独立 CLI | **内置进 kubectl**（`kubectl apply -k`） |

**何时用哪个**（第 9 章详述决策树）：

- **用 Helm**：你要复用/分发整套应用（装 cert-manager、GPU Operator、自己团队的标准化推理 Chart）、需要版本与回滚、参数化维度多。
- **用 Kustomize**：你的清单是"一份 base + 几个环境小 patch"，团队对 Go template 普遍不熟、希望输出"可读的纯 YAML"、用 GitOps（ArgoCD/Flux）原生管理。
- **都不用**：超简单单文件、或反过来极复杂需要编程逻辑——后者该上 Operator 或专用配置语言（CUE/Jsonnet）。

实践中大量团队**两者混用**：用 Helm 装第三方组件（享受现成 Chart + 版本），用 Kustomize 管自己的简单服务（base + 环境叠加）。ArgoCD/Flux 两者都原生支持。

## 1.6 Helm 在 AI 平台中的具体落点

把上面的抽象落到 AI 基础设施，Helm 无处不在：

| 场景 | 怎么用 Helm |
|---|---|
| 装 GPU Operator | `helm install gpu-operator nvidia/gpu-operator` —— 一键装好驱动/runtime/DevicePlugin/DCGM/在离线升级，参数化（MIG strategy、driver 版本）靠 values |
| 装 KubeRay | 官方 `ray` Chart，values 里开/关 operator、设镜像 |
| 装 KServe | 官方 Chart，参数化各组件副本与 knative 依赖 |
| 装 Volcano（Gang 调度） | 官方 Chart |
| 装推理监控栈 | `kube-prometheus-stack` Chart（Prometheus + Grafana + AlertManager + 一堆 ServiceMonitor） |
| 内部 LLM 推理服务 | 自研 Chart：副本/GPU 数/模型路径/域名/资源全参数化，dev/staging/prod 三套 values |
| 训练任务模板 | 把 PyTorchJob/容错配置打成 Chart，复用 |
| 装模型镜像预热 Agent、镜像懒加载（nydus/stargz） | 都以 Chart 分发 |

> 不懂 Helm 的 AI 平台工程师，会卡在"连组件都装不上"的第一步；懂了 Helm，你就能把团队的所有 K8s 部署标准化、版本化、自动化。

## 本章小结

裸 `kubectl apply` 在 demo 够用，但管理"多环境、多版本、可回滚、可复用"的整套 K8s 应用清单时会陷入四宗罪：环境差异靠复制、升级无版本无回滚、依赖靠手动按序 apply、复用靠 sed。Helm 借鉴操作系统包管理器，把"一整套清单"提升为"带参数、带版本、带依赖的软件包（Chart）"，用 Release 记录每次发布并可一键回滚，从根本上解决这四件事。Helm 经历 v1（无模板）→ v2（Go template + 集群内 Tiller，但 Tiller 是高权限后门）→ **v3（删 Tiller，纯客户端渲染，受调用者 RBAC 约束，Release 存 namespace 内 Secret）** 三代，v3 是当前稳定版本。它与 Kustomize（无模板 overlay 叠加）是两种哲学，常混用。在 AI 平台，从 GPU Operator、KubeRay、KServe、Volcano 到内部推理/训练模板，Helm 是应用分发与发布的通用语言。

**参考来源**

- [Helm 官方文档](https://helm.sh/zh/docs/)
- [Helm 架构（v3）](https://helm.sh/zh/docs/topics/architecture/)
- [Helm v3 删除 Tiller 的设计说明](https://helm.sh/zh/docs/faq/#removal-of-tiller)
- [Kustomize 官方](https://kustomize.io/)
- [Chart 仓库 Artifact Hub](https://artifacthub.io/)
