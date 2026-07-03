# 5. 核心模块：从 Chart 到 Release 的每个零件

> 一句话理解：本章把 Helm 拆成可独立理解的模块——Chart 仓库/OCI（分发）、依赖解析（组合）、模板引擎（渲染）、values 合并（参数）、Release 存储（版本记录）、CLI（入口）、Hook/Test（一次性动作与测试）、post-renderer（逃生舱）、Chart Signing（完整性），并辨析 `lookup`/`tpl`/`required` 等易错函数。

## 5.1 Chart 仓库与 OCI registry（分发层）

### 传统 Chart 仓库

一个 Chart 仓库 = 一个 HTTP server + 根目录 `index.yaml`。`index.yaml` 是所有 chart 的索引：

```yaml
apiVersion: v1
generated: "2026-07-04T..."
entries:
  gpu-operator:
    - version: v24.6.0
      appVersion: "24.6.0"
      urls:
        - https://nvidia.github.io/gpu-operator/charts/gpu-operator-v24.6.0.tgz
      digest: 9f2b...            # .tgz 的 SHA256
      created: "2026-06-01T..."
  gpu-operator:
    - version: v23.9.0
      ...
```

`helm repo add nvidia https://nvidia.github.io/gpu-operator` → `helm repo update`（拉最新 index）→ `helm search repo gpu-operator`（在 index 里搜）→ `helm install gpu-op nvidia/gpu-operator`。

### OCI registry（当前推荐）

把 Chart 当 OCI 制品（image manifest，mediaType `application/vnd.cncf.helm.chart.content.v1.tar+gzip`）推到任意 OCI registry：

```bash
# 推
helm package mychart/                      # 生成 mychart-1.4.2.tgz
helm push mychart-1.4.2.tgz oci://registry.example.com/charts

# 拉/装
helm pull oci://registry.example.com/charts/mychart --version 1.4.2
helm install myrelease oci://registry.example.com/charts/mychart --version 1.4.2
```

OCI 的优势（相对传统 repo）：

- **复用现有 registry**（Harbor/ACR/ECR/GHCR/自建 distribution），统一镜像与 chart 的存储/权限/复制/扫描/签名。
- **内容寻址 + 可复制**：registry 间的复制、签名（cosign/Sigstore）、漏洞扫描都现成。
- **更好的多租户/权限**：registry 的 RBAC 直接管 chart 访问。
- **更稳定**：不依赖一个 `index.yaml` 大文件，按 chart/版本分片。

`helm registry login` 鉴权，`helm push`/`pull` 推拉。**官方已把 OCI 作为推荐分发方式**，传统 Chart 仓库仍支持但不再获得新能力。

> **生态导航**：搜现成 Chart 用 [Artifact Hub](https://artifacthub.io/)（CNCF 的包中心，聚合各 repo/OCI 的 chart）。

## 5.2 依赖解析（组合层）

`Chart.yaml` 声明依赖：

```yaml
dependencies:
  - name: redis
    version: 18.x.x
    repository: https://charts.bitnami.com/bitnami
    condition: redis.enabled          # 父 values 的 redis.enabled=false 则不装
    alias: cache                      # 在父 values 里用 cache: {...} 而非 redis: {...}
    import-values:                    # 把子的某值导出到父
      - child: service.port
        parent: redisPort
    tags: [cache]                     # 可用 --tags cache 启/禁
```

`helm dependency update`：读 dependencies，下载到 `charts/` 目录，生成 `Chart.lock`（锁定版本，类比 package-lock）。安装父 chart 时子 chart 一起渲染安装。

**父子 values 隔离**：

- 父不能直接 <code v-pre>{{ .Values.redis.x }}</code>（那是父自己的 values）。
- 父给子传值：在父 `values.yaml` 里用**子 chart 名（或 alias）做键**：
  ```yaml
  # 父 values.yaml
  redis:                 # 子 chart 名
    architecture: replication
    auth:
      password: "secret"
  ```
- 子 chart 内部读到的是它自己的 `.Values.architecture`（合并了子的 values.yaml + 父传来的）。
- 跨父子共享用 `global`：父和所有子都能读 `.Values.global.x`。

## 5.3 模板引擎（渲染层）

`pkg/engine` 渲染流程：

1. 遍历 `templates/`（递归），跳过 `_*.tpl`（只 `define` 不产文档）。
2. 对每个文件，以 Go `text/template` + Sprig + Helm 扩展函数渲染，上下文对象 = `{ Values, Release, Chart, Files, Capabilities, Template }`。
3. 对渲染结果做 YAML 文档拆分（`---` 分隔），校验语法。
4. 把 NOTES.txt、tests/、hook 资源分类标记。
5. 普通资源按"资源类型优先级"排序（CRD 最先、workloads 较后），hook 按 weight。

### 易错函数辨析

| 函数 | 作用 | 易错点 |
|---|---|---|
| <code v-pre>{{ .Values.x \| default "y" }}</code> | x 为空时用 "y" | `default` 对 `0`/`false`/`""`/`nil` 都判空——数字 0 会被当空 |
| <code v-pre>{{ .Values.x \| required "必须填" }}</code> | x 为空则**渲染报错中止** | 强制必填字段用它，避免 `<no value>` |
| <code v-pre>{{ .Values.x \| quote }}</code> | 加引号 | 字符串里含特殊字符（`:`、`#`、`{}`）必须 quote，否则 YAML 解析错 |
| <code v-pre>{{ toYaml .Values.x \| nindent 8 }}</code> | 对象转 YAML + 缩进 | 缩进必须对齐，差一个空格就 YAML 错 |
| <code v-pre>{{ include "name" . }}</code> | 调命名模板 | 传 `.`（整个上下文），不是 `.Values` |
| <code v-pre>{{ tpl .Values.tplStr . }}</code> | 把字符串**当模板再渲染** | 用户提供的 values 字符串里能嵌 <code v-pre>{{ }}</code>，慎防注入 |
| <code v-pre>{{ lookup "v1" "ConfigMap" "ns" "name" }}</code> | 渲染时**实时查集群** | 见下，GitOps 慎用 |

### `lookup`：延迟绑定（双刃剑）

`lookup` 让模板在渲染时**查询目标集群的实时状态**：

```yaml
{{- $existing := lookup "v1" "Secret" .Release.Namespace "tls-cert" -}}
{{- if $existing -}}
tls.crt: {{ $existing.data["tls.crt"] }}
{{- else -}}
# 首次安装时还没证书，先生成占位或调用 cert-manager
{{- end -}}
```

用途：让 chart 自适应集群现状（已存在证书就复用、按节点数算副本）。**但风险**：

- 渲染结果**依赖集群状态** → 同一份 chart+values 在不同集群渲染出不同清单 → **破坏 GitOps 的"Git 是唯一真相"**（Git 里存的不等于集群里跑的）。
- `helm template`（离线渲染）没有集群，`lookup` 返回空，渲染结果与真实 install 不一致。
- **建议**：GitOps 场景尽量不用 `lookup`；必须用时，文档明确说明它的副作用，并在 values 里提供开关。

## 5.4 values 合并算法（参数层）

合并不是简单的"字典覆盖"，而是**深合并（deep merge）**：

- **map**：递归合并（子键被父的同名键深合并，不是整体替换）。
- **list**：**整体替换**（不按 index 合并）。这是最易踩的点——你想"给现有 env 列表加一个变量"，必须用 `+` 拼接或 Helm 的 `mergeOverwrite`，而不是靠 values 覆盖（会替换整个列表）。

优先级（低 → 高）：

1. 子 chart 自己的 `values.yaml`。
2. 父 chart 的 `values.yaml`（含父对子的段）。
3. `-f extra.yaml`（可多个，后者覆盖前者）。
4. `--set a.b=c`（可多个）。
5. `--set-string a.b=c`（强制字符串，防 `--set port=8080` 被当数字/`--set enabled=true` 当布尔——其实 `--set` 会按字面量推断类型，`8080` 当数字、`true` 当布尔，要纯字符串必须 `--set-string`）。

> **`--set` 语法**：`--set a.b.c=v`（嵌套）、`--set list[0]=v`（列表下标）、`--set list={a,b,c}`（列表）、`--set 'a.b\=c=d'`（值里含等号/逗号要转义）。复杂结构优先用 `-f`，`--set` 只用于少量覆盖。

## 5.5 Release 存储（版本记录层）

如第 3 章所述，每个 revision = 一个 Secret：

```
Name:   sh.helm.release.v1.myrelease.v1
Type:   helm.sh/release.v1
Namespace: prod
Annotations:
  modifiedAt: "1719..."
  version: "1"
Data:
  release: <gzip+base64 of protobuf Release{ name, namespace, chart, config(values), info(status, ...), version }>
```

`pkg/storage/driver` 抽象了存储后端（`Secret`/`ConfigMap`/`Memory`），`pkg/storage` 之上是 release 的 CRUD。`helm history`/`list`/`get`/`status` 都从这里读。

**历史上限**：`helm upgrade --history-max 10`（v3.5+，或在环境变量/配置里设）——超过上限自动删最旧 revision Secret，防止 etcd 膨胀。生产必设。

## 5.6 CLI（入口层）

`pkg/cli` + cobra 子命令。常用：

| 命令 | 用途 |
|---|---|
| `helm create NAME` | 生成一个标准 Chart 骨架（带 deployment/service/hpa/ingress 模板） |
| `helm lint CHART` | 静态检查 Chart（模板语法、必填字段、命名） |
| `helm template [NAME] CHART` | **离线渲染**，打印清单不 apply（GitOps/CI 必备） |
| `helm install/upgrade/rollback/uninstall` | Release 生命周期（第 4 章） |
| `helm package` / `push` / `pull` | 打包/推/取 |
| `helm dependency build/update` | 依赖管理 |
| `helm repo add/update/list/remove/index` | Chart 仓库管理 |
| `helm registry login/logout` | OCI registry 鉴权 |
| `helm history/list/status/get(values/manifest/all)` | 查 release |
| `helm test` | 跑 Chart 的 tests/（见下） |
| `helm search repo/hub` | 搜 chart |
| `helm upgrade --install` | "存在则升级，不存在则装"（CI/CD 幂等） |
| `helm diff upgrade ...`（helm-diff 插件） | 渲染并 diff 两个版本清单（发布前 review 必备） |

## 5.7 Hook 与 `helm test`（一次性动作与测试）

### Hook

注解驱动的时序动作（第 3、4 章已述）：

| Hook | 时机 |
|---|---|
| `pre-install`/`post-install` | install 前后 |
| `pre-upgrade`/`post-upgrade` | upgrade 前后 |
| `pre-rollback`/`post-rollback` | rollback 前后 |
| `pre-delete`/`post-delete` | uninstall 前后 |
| `test` | 仅 `helm test` 时跑 |

配套注解：`helm.sh/hook-weight`（顺序，数字小先）、`helm.sh/hook-delete-policy`（hook-succeeded/hook-failed/before-hook-creation，控制 Job 是否清理）。

### `helm test`

`templates/tests/` 下的资源（通常是 Pod）标 `helm.sh/hook: test`，`helm test myrelease` 会运行它们。典型用法：装完服务后跑一个 curl Pod 验证 `/health`：

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "mychart.fullname" . }}-test"
  annotations:
    "helm.sh/hook": test
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox
      command: ['wget', '--spider', '--timeout=10', '{{ include "mychart.fullname" . }}:{{ .Values.service.port }}/health']
```

`helm test` 是"安装后冒烟测试"的官方机制，CI 里 `helm install --wait && helm test` 很常见。

## 5.8 post-renderer（逃生舱）

`helm install/upgrade --post-renderer CMD`：Helm 渲染完清单文本后，**通过 stdin 把全部清单喂给 CMD，取回 stdout 作为最终 apply 的清单**。典型：

- `--post-renderer kustomize`：套一层 Kustomize patch（注入 sidecar、改 label）。
- 自写脚本：按集群注入 OPA 注解、套 NetworkPolicy、把镜像 digest 补上。

它是"模板引擎做不到时的逃生舱"，但也让发布流程更难审计（多了一步外部逻辑），生产用要纳入 review。

## 5.9 Chart Signing（完整性）

两种机制：

1. **Helm 原生 provenance**：`helm package --sign --key KEY` 生成 `.prov` 文件（ detached PGP 签名），`helm verify` 校验。`--verify` 安装时校验。传统 repo 时代用，依赖 GPG key 分发。
2. **OCI + cosign/Sigstore**：OCI chart 用 **cosign** 签名（keyless via Fulcio/Rekor，见容器运行时第 8 章），准入控制器（如 Sigstore Policy Controller / Kyverno）在部署侧强制"只许运行已签名 chart"。**这是供应链安全的当前推荐**。

## 5.10 模块全景对照

```
入口:    helm CLI (cobra, pkg/cli)
  │
分发:    Repository(index.yaml) / OCI registry ── helm pull/push
  │
组合:    依赖解析 (Chart.yaml deps, charts/, Chart.lock)
  │
参数:    values 合并 (深合并: map递归 / list替换, 优先级 yaml<f<--set<--set-string)
  │
渲染:    模板引擎 (pkg/engine: Go template + Sprig + lookup/required/tpl)
  │
扩展:    Hook (注解时序) / post-renderer (渲染后管道) / Library Chart (模板复用)
  │
发布:    install/upgrade(三方合并)/rollback/uninstall  ── pkg/action + pkg/kube
  │
记录:    Release 存储 (pkg/storage, Secret 驱动, history-max)
  │
完整性:  provenance(.prov) / OCI+cosign
```

## 本章小结

Helm 的核心模块按"分发→组合→参数→渲染→扩展→发布→记录→完整性"分层：**Chart 仓库/OCI registry** 分发（OCI 是当前推荐，复用 registry 的权限/复制/扫描/签名），**依赖解析**用 `Chart.yaml dependencies` 组合子 chart（父子 values 隔离、`global` 共享、condition 开关、import-values 导出），**模板引擎**是 Go template + Sprig + Helm 扩展（注意 `default`/`quote`/`required`/`lookup`/`tpl` 的易错语义，`lookup` 会破坏 GitOps 纯净需慎用），**values 合并**是深合并（map 递归、list 整体替换，优先级 `yaml < -f < --set < --set-string`），**Release 存储**是 Secret（`history-max` 防膨胀），**CLI** 提供 lint/template/install/upgrade/rollback/test 等子命令，**Hook/test** 注解驱动时序动作与冒烟测试，**post-renderer** 是渲染后逃生舱，**Chart Signing** 从 PGP provenance 演进到 OCI+cosign。把这十个模块的功能与边界记牢，遇到任何 Helm 行为都能定位到对应模块。

**参考来源**

- [Helm 命令参考](https://helm.sh/zh/docs/helm/)
- [OCI for Helm](https://helm.sh/zh/docs/topics/registries/)
- [依赖管理](https://helm.sh/zh/docs/helm/helm_dependency/)
- [Chart Hooks](https://helm.sh/zh/docs/charts_hooks/) / [Chart Tests](https://helm.sh/zh/docs/chart_tests/)
- [post-renderer](https://helm.sh/zh/docs/topics/advanced/#post-rendered)
- [provenance / 签名](https://helm.sh/zh/docs/provenance/)
