# 8. 企业生产实践：在真实 AI 平台里用 Helm

> 一句话理解：本章把 Helm 从"会用"推进到"用好、好治理"——重点回答三个生产级问题：**多环境怎么管 values**（不靠 copy-paste）、**敏感数据怎么不进 Git**（不靠 sed 改 Secret）、**chart 怎么当一等公民进 CI/CD**（不靠人肉 helm install）；并给出 AI 推理服务、Ray 集群、GPU 配额三个真实落地案例。

## 8.1 多环境 values 管理：分层而非复制

最常见的反模式是为每个环境复制一份完整 `values.yaml`（`values-dev.yaml`、`values-prod.yaml`、`values-staging.yaml`），改一个字段要同步改三份，迟早漂移。生产级做法是**分层叠加**：

```
chart/
├── values.yaml              # 基线（所有环境共享的默认值）
└── values/
    ├── dev.yaml             # 仅写与基线的差异
    ├── staging.yaml
    └── prod.yaml            # 仅写与基线的差异
```

部署时按顺序叠加（第 2 章的优先级：基线 < `-f` < `--set`）：

```bash
helm upgrade --install inference ./chart \
  -f values.yaml \
  -f values/prod.yaml \
  --set image.tag=$(git rev-parse --short HEAD)
```

对 AI 推理服务，典型分层是：

| 字段 | 基线 `values.yaml` | `dev.yaml` | `prod.yaml` |
|---|---|---|---|
| `replicaCount` | 1 | 1 | 8 |
| `image.tag` | latest | dev | 0.7.0（钉死版本） |
| `resources.limits.nvidia.com/gpu` | 1 | 1 | 1（配 GPUOperator 用 MIG 时改） |
| `autoscaling.enabled` | false | false | true（HPA + KEDA） |
| `ingress.enabled` | false | true | true |
| `model.maxModelLen` | 4096 | 4096 | 32768 |

> **经验**：`prod.yaml` 里**永远钉死 `image.tag`**，绝不用 `latest`。否则"三方合并保留字段"会在你不知情时把一个旧 tag 当成"没改"而保留——可观测性灾难。

## 8.2 敏感数据：Secret 不进 Git

`values.yaml` 进 Git，但数据库密码、API key、模型仓库的 HF token 绝不能进。三种生产级方案，按成熟度递增：

**方案 A：`--set` 临时注入（最小可用）**

```bash
helm upgrade inference ./chart \
  --set secret.hfToken=$HF_TOKEN \
  --set secret.dbPassword=$DB_PASSWORD
```

缺点：token 会出现在 shell history、`helm history` 输出里。**只适合临时调试**。

**方案 B：secrets.yaml + `.gitignore`（团队常用）**

```bash
# .gitignore
secrets.yaml

# 部署
helm upgrade inference ./chart -f values/prod.yaml -f secrets.yaml
```

`secrets.yaml` 里只放 `secret:` 段，通过 Jenkins/GitLab CI 的 secret 注入到 runner 再渲染。缺点：每个环境一个 secrets 文件，轮换麻烦。

**方案 C：External Secrets Operator（生产推荐）**

chart 模板里**不写明文**，只写一个 `ExternalSecret` 指向 Vault / AWS Secrets Manager / GCP Secret Manager：

```yaml
# templates/externalsecret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: {{ include "app.fullname" . }}-secret
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: inference-secret      # 真实 K8s Secret 由 ESO 创建
  data:
    - secretKey: hfToken
      remoteRef:
        key: ai/inference/prod  # Vault 路径
        property: hfToken
```

模板里用 `secretKeyRef: inference-secret` 引用即可。这样**轮换密钥不用改 chart、不用重新部署**——ESO 会定时刷新。这是 AI 平台对接企业密钥基础设施的标准姿势。

> **与 Helm 的契合点**：三方合并会**保留** ESO 创建的 Secret 的 `resourceVersion` 等集群字段（因为 chart 没改它们），所以 ESO 后台刷新不会和 `helm upgrade` 打架。

## 8.3 把 chart 当一等公民：CI/CD 流水线

生产里 `helm install` 永远不该由人在笔记本上敲。两种主流流水线形态：

### 形态 A：Push 型（Jenkins / GitLab CI / GitHub Actions）

chart 仓库与 app 代码分离时，典型 PR 合并后的流水线：

```yaml
# .github/workflows/release-chart.yml（简化）
- 打包 chart：helm package ./chart --version $SEMVER --app-version $APPVER
- 签名：cosign sign --key $KEY $OCI_REF           # 第 5.9 节
- 推 OCI：helm push inference-$SEMVER.tgz oci://registry.company.com/charts
- 触发部署：给 argo-cd application 发 sync 信号 / 或直接
           helm upgrade -i inference oci://.../inference --version $SEMVER -f values/prod.yaml
```

### 形态 B：Pull 型 / GitOps（Argo CD / Flux）—— 生产推荐

GitOps 把"集群状态"的唯一真相源变成 **Git 仓库**，而不是人敲的命令。Helm 在其中的角色变成**渲染器**：

```
Git 仓库（声明式）
  └── environments/prod/inference/
        ├── Chart.yaml          → 指向 oci://.../inference:0.7.0（Chart 来源）
        └── values.yaml         → 本环境的覆盖值
            │
            ▼
   Argo CD（pull）→ helm template → 三方合并 apply 到集群
```

**为什么 GitOps + Helm 是天作之合**：

1. **每次变更可审计**：`git log` 就是部署历史，比 `helm history` 更可信（`helm history` 能被 `helm rollback` 改写，git 不能）。
2. **三方合并的价值被放大**：GitOps 控制器频繁 sync，三方合并确保它不会冲掉 HPA/控制器做的弹性伸缩——这正是 GitOps "声明式 + 不破坏现场"的根基。
3. **漂移检测**：Argo CD 能检测"集群现状 ≠ Git 声明"，发出告警。

> **避坑**：GitOps 下**不要**再让人在集群里 `kubectl scale` 或 `helm upgrade`——两个真相源打架。要改副本数，改 Git 里的 `values.yaml`。

### 一个真实的 AI 推理服务 Argo CD Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: inference-prod
spec:
  source:
    repoURL: https://github.com/company/infra-deploy
    path: environments/prod/inference
    plugin:                    # 或用 Helm source type
      env:
        - name: HELM_VALUES
          value: |
            image:
              tag: 0.7.0
            replicaCount: 8
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated: { prune: true, selfHeal: true }   # 漂移自动纠正
```

`selfHeal: true` 配合 Helm 三方合并：控制器删掉被 chart 移除的字段、保留人工未改的 HPA 弹性值——这正是第 3.4 节规则在 GitOps 下的长期运行体现。

## 8.4 落地案例一：vLLM / Triton 推理服务

社区官方都有 Helm chart（`vllm-chart`、NVIDIA 的 `triton-inference-server`）。AI 平台工程师的常见工作是**写一个 wrapper chart，依赖上游 chart 并覆盖 values**：

```yaml
# Chart.yaml
apiVersion: v2
name: company-inference
version: 1.4.0
appVersion: 0.7.0
dependencies:
  - name: vllm                  # 上游 chart
    version: "0.1.*"
    repository: "oci://registry.company.com/charts"
    import-values:              # 把子 chart 的输出导到父 chart
      - child: service.port
        parent: vllmServicePort
```

```yaml
# values/prod.yaml：覆盖子 chart
vllm:
  image:
    tag: 0.7.0-cuda12           # 钉死
  model:
    name: meta-llama/Llama-3-70B-Instruct
    maxModelLen: 32768
  resources:
    limits: { nvidia.com/gpu: 4 }   # 4 张 A100
  extraArgs:
    - "--tensor-parallel-size=4"    # 张量并行
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 6
```

**生产要点**：

- `--tensor-parallel-size` 必须和 `limits.nvidia.com/gpu` 一致，否则 Pod 起不来——这种"两个 values 字段必须匹配"的约束，用第 9 章的 `values.schema.json` 强制校验。
- 大模型加载慢（70B 加载要几分钟），`helm upgrade --wait` 的超时要设到 `900s` 以上，否则 `--wait` 误判失败触发 `--atomic` 回滚，而回滚又要重新加载几分钟。
- 模型权重放 PVC（带 `resource-policy: keep`，见第 7 章场景 7），`helm uninstall` 不删权重，重装省下下载时间。

## 8.5 落地案例二：Ray 集群（RayCluster chart）

Ray 的官方 chart（`ray-cluster`）是 Helm 表达"有头有工作节点、有依赖顺序"这类复杂拓扑的好例子。一个 Ray Serve 推理集群的 values 片段：

```yaml
head:
  replicas: 1                   # 头节点固定 1 个
  resources:
    limits: { nvidia.com/gpu: 1 }
  rayStartParams:
    dashboard-host: "0.0.0.0"

worker:
  replicas: 4                   # 工作节点
  minReplicas: 2                # K8s 扩缩容下限
  maxReplicas: 16
  resources:
    limits: { nvidia.com/gpu: 8 }   # 每个工作节点 8 卡
```

**与 Helm 的协同**：

- Ray 自身的 autoscaler 和 K8s HPA **都**会改 `worker.replicas`（live）。Helm 三方合并保证 `helm upgrade`（换镜像）时这些弹性值不被冲掉——和第 7 章场景 3 同理。
- RayCluster 是 CRD，`helm uninstall` 时给 CRD 加 `resource-policy: keep`，否则删 CRD 会连累所有 Ray 应用一起被 K8s 垃圾回收（第 9 章）。

## 8.6 落地案例三：多租户 GPU 配额

平台给每个团队一个 namespace + ResourceQuota。用 Helm 把"配额"也当 release 管：

```yaml
# templates/quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-{{ .Values.team.name }}-gpu-quota
  namespace: team-{{ .Values.team.name }}
spec:
  hard:
    requests.nvidia.com/gpu: {{ .Values.team.gpuQuota }}   # 例如 16
    requests.memory: {{ .Values.team.memoryQuota }}
```

```bash
# 一个 chart，给 10 个团队各部署一个 release
for team in algo data infra ; do
  helm upgrade --install quota-$team ./gpu-quota-chart \
    --namespace platform-admin \
    --set team.name=$team \
    --set team.gpuQuota=${QUOTA[$team]}
done
```

**好处**：配额变更走 `helm upgrade`，有 revision 历史、可 rollback、可审计——比手写 10 份 ResourceQuota YAML 强得多。

## 8.7 chart 版本与发布策略

| 策略 | 做法 | 适用 |
|---|---|---|
| **Chart version = appVersion** | chart 版本号跟随 app，`1.2.3` 对应 app `1.2.3` | chart 与 app 强绑（自研服务） |
| **Chart version 独立** | chart `0.4.0`，appVersion `2.1.0`，chart 改 values 不动 app | chart 作为独立制品（社区 chart 如 vllm-chart） |
| **OCI tag = git sha** | `oci://.../inference:abc1234`，每次提交一个不可变 tag | GitOps、严格可追溯 |

> **铁律**：**永远不要覆盖已发布的 chart 版本**。OCI registry 里的 `inference:0.7.0` 一旦推过，就不可变；要改就发 `0.7.1`。覆盖会让 `helm rollback` 回到"同名但内容变了"的版本，破坏可重现性。

金丝雀 / 蓝绿用 chart 实现：

- **金丝雀**：同一 chart 两个 release（`inference`、`inference-canary`），values 里给 canary 不同的镜像 tag 和更少的副本，用 Service 的 `weight` 切流。
- **蓝绿**：两个 release（`inference-blue`、`inference-green`），切换 Service/Ingress 的 selector。回滚 = 切 selector，不重新部署。

## 8.8 可观测性与常见踩坑

**Release 可观测**：

```bash
helm list -A                  # 所有 namespace 的 release
helm history inference -n prod # revision 历史
helm get values inference -n prod --revision 4   # 某一版的 values
helm get manifest inference -n prod              # 当前渲染清单
```

**Prometheus 监控**：Helm 本身没有 metrics，但 chart 模板里渲出的 Service / Pod 的 metrics 是观测对象。关注：HPA 目标值、PVC 用量、Pod 重启次数（推理 OOM 常见）。

**常见踩坑表**：

| 症状 | 原因 | 解法 |
|---|---|---|
| `helm upgrade` 后 PVC 里的模型权重没了 | 没加 `resource-policy: keep` | PVC/Secret 加该注解（第 7 章场景 7） |
| `helm rollback` 报 "no revisions" | 用了 `helm uninstall --keep-history` 之外的方式清过历史 | 重新 install；提前用 `--keep-history` |
| GitOps 反复 sync 同一资源 | `selfHeal` + 三方合并与某控制器写的字段冲突 | 把该字段纳入 chart 管理，或用 `lookup` 豁免 |
| `--wait` 误判大模型加载失败 | 超时太短 | timeout 调到 900s+，或用 readinessProbe 的 `failureThreshold` |
| `helm upgrade` 把 HPA 扩出来的副本数冲回 | 该字段在 chart 里也声明了（chart 改了→用 new） | 把副本数完全交给 HPA，chart 里不写 `replicaCount` 或置 null |
| chart 改不动某字段 | 该字段被 `lookup` 或外部控制器锁定 | `helm get manifest` 对比；用 post-renderer 改 |
| list 型字段（如 env）升级后部分丢失 | strategic-merge-patch 按 merge key 合并，你的 list 缺 key | 给 list 项加稳定的 name 作为 merge key |

## 本章小结

- **多环境用分层 values，不复制**：基线 + `values/<env>.yaml` 差异叠加；`prod` 永远钉死镜像 tag。
- **敏感数据用 External Secrets Operator**：chart 只引用，明文不进 Git；轮换靠 ESO 定时刷新。
- **GitOps（Argo CD / Flux）+ Helm 是生产标配**：Git 是唯一真相源，三方合并让 GitOps 的频繁 sync 不破坏 HPA/控制器做的弹性伸缩——这正是 Helm 在 GitOps 下的根本价值。
- **三个 AI 落地案例**：vLLM/Triton 推理服务（wrapper chart + 上游依赖）、Ray 集群（依赖顺序 + CRD 保留策略）、多租户 GPU 配额（一 chart 多 release）。
- **版本铁律**：永不覆盖已发布的 chart 版本；金丝雀/蓝绿靠多 release + 流量切换实现。

**参考来源**

- [Argo CD + Helm 官方文档](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/)
- [External Secrets Operator](https://external-secrets.io/)
- [vLLM Helm Chart](https://github.com/vllm-project/vllm-operators)
- [RayCluster Helm Chart](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- 第 3.4 节三方合并规则、第 5.9 节 cosign 签名、第 7 章场景 7（resource-policy）
