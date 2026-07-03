# 2. 核心思想：Chart、values、template、Release

> 一句话理解：Helm 的全部设计可以浓缩成五个名词——**Chart（一套带参数的模板，即"软件包"）**、**values（参数）**、**template（Go template + Sprig 函数渲染出 YAML）**、**Release（一次带版本的安装实例）**、**Repository/依赖（分发与组合）**；理解了这五个，Helm 就理解了 80%。

## 2.1 Chart：K8s 应用的"软件包"

**Chart 是 Helm 的基本单位**：它是一个目录（或打包后的 `.tgz`），描述**一整套相关的 K8s 资源如何被生成**。一个最小 Chart 的结构：

```
mychart/
├── Chart.yaml            # Chart 的元数据：名字、版本、描述、依赖、类型
├── values.yaml           # 默认值（渲染模板时用）
├── charts/               # 该 chart 依赖的子 chart（可选）
├── templates/            # 模板文件（渲染出 K8s 清单）
│   ├── _helpers.tpl      # 可复用的命名模板（partial）
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── NOTES.txt         # 安装成功后打印给用户看的提示文本
├── templates/tests/      # helm test 跑的测试 Pod（可选）
└── README.md             # 给人读的说明
```

`Chart.yaml` 的关键字段：

```yaml
apiVersion: v2                       # v2 是 Helm 3 的 Chart API 版本
name: mychart                         # Chart 名字
description: A GPU inference service chart
type: application                     # application（默认）或 library
version: 1.4.2                        # Chart 自己的版本（Sematic Versioning）
appVersion: "v0.21.0"                 # 应用/镜像版本（仅给人读，不参与计算）
icon: https://.../logo.png
home: https://github.com/org/mychart
sources:
  - https://github.com/org/mychart
maintainers:
  - name: platform-team
keywords: [llm, inference, gpu]
dependencies:                         # 依赖的子 chart
  - name: redis
    version: 18.x.x
    repository: https://charts.bitnami.com/bitnami
    condition: redis.enabled
```

三个**关键概念辨析**：

| 字段 | 含义 | 易混淆点 |
|---|---|---|
| `version` | **Chart 自己的版本**（模板/默认值改了就要升） | Helm 用它做依赖解析、仓库索引 |
| `appVersion` | **被打包应用/镜像的版本** | 只是字符串给人读，Helm 计算时**不读它**；很多人误以为改 appVersion 就换了镜像，其实镜像 tag 是 `values.yaml` 里的 `image.tag` |
| `apiVersion` | **Chart 格式版本**（v1 = Helm 1 旧格式，v2 = Helm 3） | 不是 K8s 的 apiVersion |

> **踩坑预警**：改了镜像却没生效，第一个查的是 `values.yaml` 的 `image.tag`，而不是 `Chart.yaml` 的 `appVersion`。`appVersion` 是装饰性的。

## 2.2 values：Chart 的参数

`values.yaml` 提供模板渲染的默认值：

```yaml
# values.yaml
replicaCount: 2

image:
  repository: ghcr.io/org/vllm
  tag: "0.6.3"
  pullPolicy: IfNotPresent

model:
  name: "meta-llama/Llama-3-8B-Instruct"
  maxModelLen: 8192

resources:
  limits:
    nvidia.com/gpu: 1
    memory: 24Gi
  requests:
    cpu: "4"
    memory: 16Gi

ingress:
  enabled: true
  host: inference.example.com

serviceAccount:
  create: true
  name: ""
```

模板里用 <code v-pre>{{ .Values.键 }}</code> 取值：

```yaml
# templates/deployment.yaml（节选）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: server
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          resources: {{- toYaml .Values.resources | nindent 12 }}
          env:
            - name: MODEL_NAME
              value: {{ .Values.model.name | quote }}
```

**values 的分层与覆盖顺序**（从低到高优先级，第 5 章详述合并算法）：

```
subchart 的 values.yaml        ← 子 chart 默认值（在被引用时）
  < parent 的 values.yaml       ← 父 chart 默认值（可覆盖子 chart）
    < 父 values.yaml 里的 "子chart名:" 段   ← 父 chart 显式给子 chart 的值
      < -f values-prod.yaml     ← 命令行指定的额外 values 文件
        < --set key=val         ← 命令行 --set（最后覆盖，优先级最高）
          < --set-string        ← 强制字符串类型（防数字/布尔误判）
```

> **`global`**：父 chart 和所有子 chart 都能读到 `.Values.global`，用于放"全局共享"的值（如 image registry、镜像拉取密钥、storageClass）。普通 values 是父子**隔离**的（父不能直接读子的、子不能直接读父的），只有 `global` 例外。

## 2.3 template：Go template + Sprig

Helm 的模板引擎基于 Go 标准库的 `text/template`，并叠加了 **Sprig 函数库**（200+ 实用函数）和 Helm 自己加的几个函数。掌握它需要理解五件事：

### 2.3.1 取值与作用域

- <code v-pre>{{ .Values.* }}</code>：取 values。
- <code v-pre>{{ .Release.* }}</code>：取本次 release 信息（`.Name`、`.Namespace`、`.Service`、`.IsInstall`、`.IsUpgrade`、`.Revision`）。
- <code v-pre>{{ .Chart.* }}</code>：取 Chart.yaml 内容（`.Chart.Version`、`.Chart.AppVersion`、`.Chart.Name`）。
- <code v-pre>{{ .Files.* }}</code>：取 chart 目录里的非模板文件。
- <code v-pre>{{ .Capabilities.* }}</code>：取目标集群能力（K8s 版本、可用 API 版本）。
- `.` 本身 = 整个上下文对象（传给 `include`/`define` 时常用）。

### 2.3.2 控制结构

```yaml
{{- if .Values.ingress.enabled }}     # 条件
apiVersion: networking.k8s.io/v1
kind: Ingress
{{- end }}

{{- with .Values.model }}              # 改变作用域：进入 model 子对象
  - name: MODEL_NAME
    value: {{ .name | quote }}          # 这里 . 指 model，.name = model.name
{{- end }}

{{- range $key, $val := .Values.env }}  # 循环
  - name: {{ $key }}
    value: {{ $val | quote }}
{{- end }}
```

<code v-pre>{{- }}</code> 里的 `-` 是**空白修剪符**：去掉 <code v-pre>{{</code>/<code v-pre>}}</code> 相邻的换行与空格，防止渲染出来的 YAML 有空行错位（YAML 对缩进敏感，这点极重要）。

### 2.3.3 管道与函数

Go template 的管道 `|` 把前一个函数的输出作为后一个的输入，Sprig 提供了大量函数：

```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default "latest" }}"
nameOverride: {{ .Values.name | trunc 63 | trimSuffix "-" }}    # 截断到 63 字符（K8s 名字上限）再去尾 -
env: {{- toYaml .Values.extraEnv | nindent 8 }}                 # 把 map 转成多行 YAML 并缩进
```

常用 Sprig/Helm 函数：`quote`、`default`、`required`（值为空就报错中止渲染）、`trunc`、`trimSuffix`、`lower`、`replace`、`b64enc`/`b64dec`、`toYaml`/`fromJson`、`nindent`/`indent`、`join`、`splitList`、`lookup`（第 5 章）、`tpl`（把字符串当模板再渲染一次）。

### 2.3.4 命名模板（partial / `_helpers.tpl`）

`define` 定义、`include`/`template` 调用，放在以 `_` 开头的文件里（Helm 不把它当 K8s 清单渲染）：

```yaml
# templates/_helpers.tpl
{{- define "mychart.fullname" -}}
{{- printf "%s-%s" .Release.Name (default .Chart.Name .Values.nameOverride) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mychart.labels" -}}
app.kubernetes.io/name: {{ include "mychart.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
```

```yaml
# templates/deployment.yaml
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
```

`include` 比 `template` 更常用，因为它能接管道（`include "x" . | nindent 4`）。

### 2.3.5 NOTES.txt

`templates/NOTES.txt` 是模板，安装/升级成功后 Helm 把它渲染结果**打印到终端**，用于告诉用户"怎么用"（端口、域名、下一步命令）。这是良好 Chart 的标配。

## 2.4 Release：一次带版本的安装实例

**Release = 一个 Chart 在某个 namespace 的一次安装实例**。关键属性：

- **Release Name**：你给的名字（`helm install my-release mychart`），在 namespace 内唯一。
- **Revision（版本号）**：每次 `install` / `upgrade` 都让 revision **自增 1**。第一次 install = revision 1，第一次 upgrade = revision 2……
- **Release 状态**：`deployed`（已部署，最新版）/ `superseded`（被新版本取代）/ `failed`（失败）/ `pending-install`/`pending-upgrade`/`pending-rollback`（进行中，崩溃时可能卡这）/ `uninstalled`/`uninstalling`。

**Release 的存储**（v3）：每个 revision 是所在 namespace 里的一个 **Secret**，名字形如 `sh.helm.release.v1.<release>.v<revision>`，里面是 base64 编码的 release 对象（含本次用的 chart 模板、values、渲染出的清单、状态）。`helm history my-release` 就是读这些 Secret 列出来的。

> **核心洞察**：正是因为每个 revision 都把"当时用的 chart + values + 渲染清单"完整存进了 Secret，Helm 才能 `helm rollback my-release 3` ——它把第 3 版的清单重新 apply 回去，根本不需要你当时的 values 文件还在不在。**Release Secret 就是 Helm 的"undo log"**。

## 2.5 Repository 与依赖：分发与组合

### Repository（Chart 仓库）

两种形态：

1. **传统 Chart 仓库**：一个 HTTP server，根目录放 `index.yaml`（列出所有 chart 及其版本、各版本的 `.tgz` URL/SHA256），`.tgz` 包放任意位置。`helm repo add` 注册仓库 URL，`helm search repo` 在 index 里搜。
2. **OCI registry**（2022 GA）：把 Chart 直接当 OCI 制品推到任意兼容 OCI 的 registry（Harbor、ACR、ECR、GHCR、自建 distribution）。引用形如 `oci://registry.example.com/charts/mychart`，带签名/扫描/复制等所有 OCI 能力。**这是当前推荐方向**，传统 Chart 仓库逐渐被取代。

`helm pull` / `helm push`（OCI 用 `helm push chart.tgz oci://...`）用于取/存 chart 包。

### 依赖（dependencies / Subchart）

一个 Chart 可以声明依赖别的 Chart（`Chart.yaml` 的 `dependencies`）。`helm dependency update` 会把子 chart 下载到 `charts/` 目录。安装父 chart 时，子 chart **一起被渲染、一起安装**，且：

- 父 chart 用 `values.yaml` 里以**子 chart 名为键**的段，给子 chart 传值（`redis: { architecture: replication }`）。
- 父子 chart 的模板**互相隔离**（各自一套 `.Values`、`.Templates`），只能通过 `global` 共享。
- 子 chart 的资源可以被父 chart **关闭**：`dependencies` 里写 `condition: redis.enabled`，父 chart values 里设 `redis.enabled: false` 就不装它。

**Library Chart**（`type: library`）：只定义命名模板（helper），**不渲染任何 K8s 资源**，被其他 chart 依赖以复用模板逻辑（如统一的 label/名字生成、公共 ConfigMap 片段）。是"模板复用"的官方机制，类比编程里的"库"。

### 依赖 vs Hook vs Operator（边界辨析）

| 机制 | 何时用 |
|---|---|
| **Subchart 依赖** | 你的应用**确实需要**附带另一个组件（如推理服务自带个 Redis 缓存），且希望随主应用一起安装/升级/卸载 |
| **Hook**（见第 5 章） | 需要在 install/upgrade 的**特定时机**跑一次性任务（迁移数据库、跑 job 初始化、注册 schema） |
| **Operator**（计划中主题） | 需要长期运行的、**集群内持续 reconcile** 的领域逻辑（监控 CR 变化、自愈、扩缩）—— Helm 只在 install/upgrade 那一刻"做一次"，不能持续观察 |

## 2.6 把五要素串起来：一次 `helm install` 发生了什么

把 Chart/values/template/Release/Repository 串成一个心智模型：

```
Chart 仓库 / OCI               ← helm pull / helm install 从这里取 Chart 包
       │ (.tgz: Chart.yaml + values.yaml + templates/)
       ▼
  加载 Chart 到内存
       │  合并 values.yaml ← -f 覆盖 ← --set
       ▼
  template 引擎渲染            ← Go template + Sprig，把 {{ }} 填成具体值
       │  产出：一组 K8s 清单（YAML）
       ▼
  记录 Release（revision N）   ← 存进 namespace 内 Secret
       │
       ▼
  把清单 apply 到 kube-apiserver  ← 用调用者的 kubeconfig（受 RBAC 约束）
       │
       ▼
  打印 NOTES.txt               ← 告诉用户怎么用
```

> 一句话：**Repository 取 Chart → values 填参 → template 渲染出清单 → Release 记录这一版 → apply 到 apiserver**。后续 `upgrade` = 换 chart/values 再走一遍，revision +1；`rollback N` = 把第 N 版的清单重新 apply。

## 本章小结

Helm 的设计围绕五个名词：**Chart**（一套带参数的模板，即"软件包"，核心是 `Chart.yaml` 元数据 + `values.yaml` 默认值 + `templates/` 模板，注意 `version`/`appVersion`/`apiVersion` 三者的区别）、**values**（参数，分层覆盖：subchart 默认 < parent 默认 < `-f` < `--set`，`global` 跨父子共享）、**template**（Go template + Sprig 函数，五要素：取值作用域/控制结构/管道函数/命名模板 `include`/NOTES.txt）、**Release**（一次带 revision 的安装实例，每版存进 namespace 内 Secret，是 Helm 的 undo log，支撑 rollback）、**Repository/依赖**（传统 Chart 仓库或 OCI registry 分发；Subchart 组合应用、Library Chart 复用模板、用 condition 开关子 chart）。把这五者串起来：仓库取 Chart → values 填参 → 模板渲染 → Release 记录 → apply 到 apiserver。这就是 Helm 的全部核心。

**参考来源**

- [Helm Chart 模板指南](https://helm.sh/zh/docs/chart_template_guide/)
- [Sprig 函数文档](http://masterminds.github.io/sprig/)
- [Chart.yaml 字段参考](https://helm.sh/zh/docs/charts/)
- [Helm 依赖管理](https://helm.sh/zh/docs/helm/helm_dependency/)
- [OCI for Helm Charts](https://helm.sh/zh/docs/topics/registries/)
