# 9. 最佳实践与避坑指南

> 一句话理解：本章是把"会跑的 chart"打磨成"好维护、好治理、好排查的 chart"的清单——分四块：**chart 设计规范**（命名、`_helpers.tpl`、values 校验）、**模板卫生**（避开 Sprig 陷阱、`lookup` 双刃剑、缩进地狱）、**升级与回滚纪律**（钉版本、不破坏弹性、保留策略）、**何时该用/不该用 Helm**（与 Kustomize 的边界）。

## 9.1 chart 设计规范

### 命名：fullname helper 是 chart 的"宪法"

每个资源都要有一个稳定、唯一、合规的 `name`（K8s 限 63 字符，DNS 子域）。**所有资源统一调同一个命名模板**，杜绝手写 name：

```gotemplate
{{- define "app.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{-   .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{-   $name := default .Chart.Name .Values.nameOverride -}}
{{-   if contains $name .Release.Name -}}
{{-     .Release.Name | trunc 63 | trimSuffix "-" -}}
{{-   else -}}
{{-     printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{-   end -}}
{{- end -}}
{{- end -}}
```

这段是 Helm 官方 `create` 生成的标准实现，**不要自己发明**。它的精妙处：release 名重复 chart 名时不重复（`myrelease` vs `myrelease-inference`），超长自动 `trunc 63`，结尾的 `-` 被 `trimSuffix` 去掉（否则 K8s 拒绝）。AI 推理服务的 Deployment、Service、PVC、HPA 全部 <code v-pre>{{ include "app.fullname" . }}</code>，命名一致，`kubectl get` 一眼能找到全套资源。

### labels：四个标准标签

```gotemplate
{{- define "app.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
```

这四个标签（`helm.sh/chart` + `app.kubernetes.io/{name,instance,managed-by}`）是 Helm 与 K8s 的**通用语言**：`helm list` 靠它们识别 release 资源，Argo CD 靠 `instance` 区分蓝绿，`kubectl` 靠 `name` 做 selector。AI 推理服务再加 `app.kubernetes.io/component: inference-server` 方便按组件筛选。

### `_helpers.tpl` 的边界

`_helpers.tpl` 放**命名模板**（`define`），不放任何输出（`_` 前缀的文件不渲染成清单）。原则：

- 命名要重复用的字符串（fullname、labels、selectorLabels、image）→ 放进去。
- 只用一次的模板 → 直接写在资源模板里，别过度抽象。
- selectorLabels 与 labels 分开：selectorLabels 必须是**不可变**的（改了 selector 老版 Pod 永远不会被选中），labels 可以加新键。

```gotemplate
{{- define "app.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

## 9.2 values 校验：`values.schema.json` 是强制契约

AI 平台的 chart 经常跨团队使用，values 写错（`gpu: "1"` 写成字符串、`tensor-parallel-size` 和 GPU 数不匹配）会导致 Pod 起不来。`values.schema.json` 把契约固化，`helm install/upgrade/lint` 时强制校验：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "replicaCount": { "type": "integer", "minimum": 1 },
    "image": {
      "type": "object",
      "properties": {
        "tag":    { "type": "string", "pattern": "^v?\\d+\\.\\d+\\.\\d+" },
        "pullPolicy": { "enum": ["Always", "IfNotPresent", "Never"] }
      },
      "required": ["tag"]
    },
    "tensorParallelSize": { "type": "integer", "enum": [1, 2, 4, 8] }
  },
  "required": ["image", "tensorParallelSize"]
}
```

```bash
$ helm install bad ./chart --set tensorParallelSize=3
Error: values don't meet the specifications of the schema(s)
... tensorParallelSize: tensorParallelSize must be one of [1,2,4,8]
```

> **AI 场景必加校验**：`tensorParallelSize` ∈ {1,2,4,8}、`gpu` 数 = `tensorParallelSize` × `pipelineParallelSize`、`maxModelLen` 上限。这类约束写进 schema，比写在 README 里等人读强一百倍。

## 9.3 模板卫生：避开四个陷阱

### 陷阱一：`lookup` 是双刃剑

<code v-pre>{{ lookup "v1" "ConfigMap" "ns" "name" }}</code> 在渲染时**实时查集群**。看上去方便（"if 已存在就跳过创建"），但破坏了 Helm 的核心承诺——**渲染是幂等、可离线、可重现的**。

```gotemplate
{{- $existing := lookup "v1" "Secret" .Release.Namespace "tls-cert" -}}
{{- if $existing }}
# 复用已有证书
{{- else }}
# 创建自签证书
{{- end }}
```

**问题**：

1. `helm template`（离线渲染）拿不到集群，`lookup` 永远返回空 → 渲染结果和真实 install 不一致，CI 里的 diff 失真。
2. Argo CD 的 dry-run 模式 `lookup` 行为又不同，导致"本地能渲染、GitOps 渲染不出来"。
3. 引入对集群状态的隐式依赖，违背"chart 是纯函数"。

**规则**：除非确有必要（迁移场景），**不用 `lookup`**。需要"已存在就跳过"的语义，用 `helm.sh/resource-policy: keep` 或 External Secrets。

### 陷阱二：缩进地狱

把一段 dict 塞进清单，永远用 `toYaml` + `nindent`（不是 `indent`）：

```gotemplate
# ✅ 正确：nindent 先换行再缩进，整块对齐
spec:
  template:
    spec:
      containers:
        - name: server
          resources:
            {{- toYaml .Values.resources | nindent 12 }}

# ❌ 错误：indent 不换行，第一行会粘在 resources: 后面
          resources:
            {{- toYaml .Values.resources | indent 12 }}    # 渲染成 "resources:limits:..."
```

`nindent`（**n**ewline + indent）总是先加一个换行——这就是为什么模板里写 <code v-pre>key:\n  {{- ... | nindent N }}</code>。第 7 章的 demo 引擎忠实实现了这个语义。

### 陷阱三：不要在模板里塞业务逻辑

模板是**渲染**，不是**编程**。下面这种就该重构成 values：

```gotemplate
{{- if eq .Values.env "prod" }}
  {{- if gt (int .Values.replicaCount) 4 }}
    {{- .Values.replicaCount }}
  {{- else }}
    {{- 4 }}
  {{- end }}
{{- else }}
  {{- 1 }}
{{- end }}
```

改成在 values 分层里直接给 `prod.yaml: { replicaCount: 8 }`，模板里就一行 <code v-pre>replicas: {{ .Values.replicaCount }}</code>。**模板保持"笨"，聪明放在 values 和 CI。**

### 陷阱四：依赖 Sprig 的非确定函数

Helm **故意删掉了** Sprig 的 `env` 和 `expandenv`（第 6 章 6.6 节），就是为了渲染可重现。同理，避免用 `randAlphaNum` 之类随机函数生成密码——同样的 chart 渲染两次结果不同，`helm diff` 永远显示变化。要生成随机密码，用 `genPassword` 但配合 `--set` 或 External Secrets 把结果固化。

## 9.4 升级与回滚纪律

### 钉版本，禁 latest

```yaml
# ❌ prod 灾难
image: { tag: latest }

# ✅ 可追溯
image: { tag: "0.7.0" }          # 或 OCI tag = git sha
```

`latest` + 三方合并 = 灾难：升级时 `old.tag == new.tag == "latest"`，Helm 判定"chart 没改镜像"，于是**保留 live 的镜像**（可能是个旧 latest），你以为升了其实没升。

### 不破坏弹性：让 HPA 管副本

一旦开了 HPA，chart 里**不要写 `replicaCount`**（或写 `null`），否则三方合并会因为"chart 改了/没改"产生歧义。把副本数完全交给 HPA，chart 只声明 `minReplicas`/`maxReplicas`。这是第 7 章场景 3 教训的生产化。

### 保留策略：CRD、PVC、证书

```yaml
metadata:
  annotations:
    helm.sh/resource-policy: keep
```

对这三类资源**必加**：

- **CRD**：删 CRD 会连带删除所有该 CRD 的实例（K8s 垃圾回收），等于删业务数据。
- **PVC**：模型权重、checkpoint 删了要重新下载几小时（甚至几十 GB）。
- **TLS 证书 / Secret**：重新签发涉及外部 CA，可能不可逆。

注意 `resource-policy: keep` 会让资源在 `helm uninstall` 后**永久残留**，要清理得手动 `kubectl delete`——所以只用在"确实要保留"的资源上。

### `--atomic` + `--wait`：失败自动回滚

```bash
helm upgrade --install inference ./chart \
  -f values/prod.yaml \
  --atomic \          # 失败自动 rollback
  --wait \            # 等 readiness
  --timeout 15m       # 大模型加载慢
```

`--atomic` 隐含 `--wait`。这是生产部署的安全网——升级失败自动回到上一版，不会把集群停在半升级状态。但**别滥用**：

- `--wait` 期间 Pod 没就绪，`--atomic` 会回滚——如果是 readinessProbe 配错，会无限回滚循环。
- 大模型加载 5 分钟，`--timeout` 必须大于加载时间，否则误判。

## 9.5 chart 测试

三层测试金字塔：

**Lint（静态检查）**

```bash
helm lint ./chart                      # 基础检查
ct lint --chart-dirs charts            # chart-testing 工具：跨版本兼容、YAML 规范
```

**单 chart 单元测试（`helm unittest` 插件）**

```yaml
# tests/deployment_test.yaml
suite: test deployment rendering
tests:
  - it: should set replicas from values
    set: { replicaCount: 3 }
    asserts:
      - equal: { path: spec.replicas, value: 3 }
  - it: should not render HPA when disabled
    asserts:
      - hasDocuments: { count: 0 }
    template: templates/hpa.yaml
```

**`helm test`（集群内冒烟）**

chart 里写 `templates/tests/test-connection.yaml`：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "app.fullname" . }}-test"
  annotations: { "helm.sh/hook": test }
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox
      command: ['wget', '--spider', '--timeout=10',
                '{{ include "app.fullname" . }}:{{ .Values.service.port }}/health']
```

```bash
helm test inference -n prod     # 起这个 Pod 跑健康检查，成功则 release 通过
```

对 AI 推理服务，`helm test` 可以发一个 `/v1/completions` 推理请求，验证模型真的加载成功（而不是 Pod ready 但模型还没 load 完）。

## 9.6 何时该用 Helm，何时不该

| 场景 | 推荐 | 理由 |
|---|---|---|
| 给团队/社区分发的可配置应用 | **Helm** | values 参数化、版本化、仓库分发是核心优势 |
| 同一应用多环境（dev/staging/prod） | **Helm** | 分层 values 天然支持 |
| 上游 chart + 少量覆盖（vllm-chart、ray） | **Helm** | 依赖机制 + override 精准匹配 |
| 单一团队、固定配置、不想学模板语法 | **Kustomize** | 无模板，纯 overlay patch，零魔法 |
| 极简 patch（改 image、加 label） | **Kustomize** | 一个 `kustomization.yaml` 搞定 |
| 需要参数化 + 逻辑分支 | **Helm** | Kustomize 不支持条件渲染 |
| GitOps 严格纯声明 | 两者皆可 | Argo CD / Flux 都原生支持 |

**核心区别**：Helm 是**模板 + 参数**（渲染期生成清单），Kustomize 是**overlay + patch**（合并已有清单）。Helm 表达力强但复杂；Kustomize 简单但无逻辑。AI 平台多数场景（推理服务、Ray、配额）参数多、有条件渲染，**Helm 更合适**；纯基础设施（给上游 operator 加个 label）用 Kustomize 更轻。

> **不要混用**：同一套资源既用 Helm 又用 Kustomize patch，会让"谁改了什么"无法追溯。选一个，贯彻到底。

## 9.7 安全最佳实践

1. **chart 来自可信仓库**：用 OCI + cosign 签名（第 5.9 节），`helm install --verify` 校验签名。
2. **Pod Security Standards**：chart 默认 `runAsNonRoot: true`、`readOnlyRootFilesystem: true`，需要特权的（GPU operator）显式开。
3. **RBAC 最小化**：chart 模板里 `ServiceAccount` + `Role/RoleBinding` 只授必要权限，别图省事用 `cluster-admin`。
4. **镜像来源**：`image.repository` 指向私有镜像仓库，加 `imagePullSecrets`；不用公网 latest。
5. **网络策略**：推理服务 chart 默认带 `NetworkPolicy`，只允许网关 namespace 访问推理端口。

## 本章小结

- **命名靠 `_helpers.tpl` 的 fullname/labels/selectorLabels**，全家资源统一调，不自造 name。
- **values 用 `schema.json` 强制契约**，AI 场景的 `tensorParallelSize`、GPU 数约束写进去，比 README 强百倍。
- **模板保持"笨"**：避开 `lookup`、用 `nindent` 不用 `indent`、逻辑放 values 不放模板、不用随机函数。
- **升级纪律**：钉版本禁 latest、开 HPA 就别写 replicaCount、CRD/PVC/证书加 `resource-policy: keep`、生产用 `--atomic --wait`。
- **三层测试**：`helm lint` / `helm unittest` / `helm test`，AI 服务在 test 里发真实推理请求验证模型加载。
- **选型**：参数化 + 条件渲染选 Helm，纯 patch 选 Kustomize，**别混用**。

**参考来源**

- [Helm Chart Best Practices（官方）](https://helm.sh/docs/chart_template_guide/getting_started/)
- [chart-testing (ct) 工具](https://github.com/helm/chart-testing)
- [helm-unittest 插件](https://github.com/quintush/helm-unittest)
- [Kustomize vs Helm](https://helm.sh/docs/intro/install/)
- 第 3.4 节三方合并、第 5.8 节 `helm test`、第 6.6 节 Sprig env 删除、第 7 章场景 7 保留策略
