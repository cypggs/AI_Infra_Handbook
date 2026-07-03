# 6. 源码分析：helm/helm 的代码地图

> 一句话理解：本章是 Helm 的"源码导游"——`helm/helm` 仓库结构清晰、分层干净（`cmd/helm` CLI 入口、`pkg/action` 业务动作、`pkg/engine` 模板渲染、`pkg/kube` 与 apiserver 交互及三方合并、`pkg/releaseutil`/`pkg/storage`/`pkg/chart` 等支撑），抓三条主线就能理解全局：**install/upgrade 怎么调到三方合并**、**模板怎么被渲染**、**Release 怎么被存储**。

## 6.1 仓库总览

[helm/helm](https://github.com/helm/helm)（Go 项目）顶层布局：

```
helm/
├── cmd/helm/                 # CLI 入口：main.go + cobra 命令注册
├── internal/                 # 内部包（不对外稳定）
├── pkg/                      # 核心库（稳定 API）
│   ├── action/               # ★ 业务动作：Install/Upgrade/Rollback/Uninstall/...
│   ├── chart/                # Chart 数据结构（Chart.yaml → Metadata, File, Loader）
│   ├── chartutil/            # Chart 工具（values 合并、CreateValues、version 约束）
│   ├── cli/                  # ★ 环境与 kubeconfig（cmd/helm 调它）
│   ├── engine/               # ★ 模板渲染引擎（Go template + Sprig）
│   ├── getters/              # HTTP/OCI 取 chart
│   ├── helm/path/            # 路径（repo cache、config dir）
│   ├── kube/                 # ★ 与 apiserver 交互 + 三方合并 Patch
│   ├── lint/                 # Chart 静态检查
│   ├── plugin/               # 插件机制（helm-diff 等）
│   ├── postrender/           # post-renderer 执行器
│   ├── release/              # Release 数据结构（Release, Status, Hook）
│   ├── releaseutil/          # ★ 清单排序、拆分、过滤
│   ├── repo/                 # Chart 仓库（index.yaml 解析、repo add/update）
│   ├── registry/             # OCI registry 客户端
│   ├── storage/              # ★ Release 存储抽象 + driver(Secret/ConfigMap/Memory)
│   └── ...
├── scripts/                  # 发布脚本
└── testdata/                 # 测试用 chart
```

> **读源码策略**：Helm 代码可读性很高，建议从一条命令（`helm install`）的入口 `cmd/helm/install.go` 一路追到 `pkg/action/install.go` → `pkg/kube`，建立"参数→渲染→合并→apply→存储"的全链路直觉，再按需深入 `engine`/`storage` 等子模块。

## 6.2 主线一：`helm install/upgrade` 的调用链

### 入口：`cmd/helm`

`cmd/helm/install.go`（cobra command）解析参数后，构造 `action.Install`：

```go
// cmd/helm/install.go（简化）
func (o *installOptions) run() error {
    action := action.NewInstall(o.cfg)        // pkg/action.Install
    action.Namespace = o.namespace
    action.Wait = o.wait
    action.Timeout = o.timeout
    action.Atomic = o.atomic
    rel, err := action.Run(chart, vals)       // vals = 合并后的 values
    ...
}
```

`action.NewInstall` 持有一个 `action.Configuration`（封装 kubeconfig、storage driver、KubeClient）。

### 动作：`pkg/action/install.go`

`action.Install.Run(chart, vals)` 的核心流程（与第 4 章时序对应）：

```go
func (i *Install) Run(chrt *chart.Chart, vals map[string]interface{}) (*release.Release, error) {
    // 1. 渲染（chartutil + engine）
    rel := i.createRelease(chrt, vals)         // 构造 release 对象
    // 2. 校验 chart（chartutil.IsInstallable 等）

    // 3. 记录 pending-install（先存 Secret，再 apply）
    rel.SetStatus(release.StatusPendingInstall, "")
    if err := i.cfg.Releases.Create(rel); err != nil { ... }

    // 4. 执行 pre-install hook
    if err := i.cfg.execHook(rel.Hooks, ...); err != nil { ... }

    // 5. 渲染 + apply（核心）
    rel, err = i.performInstall(rel, ...)      // → renderResources → kubeClient.Create/Update
    return rel, err
}
```

`performInstall` 调用 `i.cfg.renderResources`（即 `engine.Render`）渲染出清单，然后交给 `i.cfg.KubeClient.Create` 真正 apply 到 apiserver。

### upgrade 的三方合并落点：`pkg/action/upgrade.go` + `pkg/kube`

`action.Upgrade.Run` 的关键差异在它**读取上一版 release 的清单**作为"old"，与本次渲染的"new"一起交给 `pkg/kube`：

```go
func (u *Upgrade) Run(chrt *chart.Chart, vals map[string]interface{}) (*release.Release, error) {
    currentRelease, _ := u.cfg.Releases.Get(u.Name, ...lastDeployedRevision)
    // currentRelease.Manifest = 上一版渲染清单 (old)

    newRelease := u.createRelease(chrt, vals)
    // 渲染本次 (new)
    ...

    // 记录 pending-upgrade
    if err := u.cfg.Releases.Create(newRelease); err != nil { ... }

    // 调用 KubeClient.Update：三方合并的真正入口
    _, err := u.cfg.KubeClient.Update(
        parseManifests(currentRelease.Manifest), // old
        parseManifests(newRelease.Manifest),     // new
        /* force */ u.Force,
    )
    ...
}
```

`pkg/kube.Client.Update(target, current, ...)` 是**三方合并的真正所在**：

```go
// pkg/kube/client.go（简化思路）
func (c *Client) Update(original, target ResourceList, ...) (*Result, error) {
    for _, targetRes := range target {
        oldRes := findIn(original, targetRes)        // 上一版清单里的同名资源 = old chart
        liveRes := c.Helper.Get(targetRes)           // 集群现状 = live
        patch := strategicMergePatch(oldRes, liveRes, targetRes)  // 三方合并
        c.Helper.Patch(targetRes, patch)
    }
}
```

它对每个资源用 client-go 的 `StrategicMergePatchType`（有 schema 的结构化 patch）或退化到 `MergePatchType`，三路（old chart / live / new chart）算出最小 diff，再 `PATCH` 到 apiserver。这正是第 3 章三方合并语义的代码实现。

> **关键定位**：想看"Helm 升级为什么没覆盖我手动 scale 的副本"，看 `pkg/kube` 的 `Update` 和它调用的 patch 构造逻辑（`pkg/kube/resource.go`、`pkg/kube/converter.go`、依赖 `k8s.io/apimachinery` 的 strategic merge 实现）。

## 6.3 主线二：模板渲染 `pkg/engine`

`pkg/engine.Engine.Render(chrt, values)`：

```go
func (e Engine) Render(chrt *chart.Chart, values chartutil.Values) (map[string]string, error) {
    // 1. 构造上下文（.Values/.Release/.Chart/.Files/.Capabilities）
    // 2. 注册 Sprig 函数 + Helm 扩展函数（include/tpl/lookup/required/...）
    //    见 pkg/engine funcs.go
    // 3. 对每个模板文件渲染
    //    - _helpers.tpl 的 define 先收集
    //    - 其余文件作为独立模板，输出一个"文件名 → 渲染文本"的 map
    // 4. 处理子 chart：递归 Render，传各自 values（chartutil.ToRenderValues 处理父子隔离）
    return rendered, nil
}
```

**Sprig 与 Helm 扩展函数注册**在 `pkg/engine/funcs.go`：

```go
func funcMap(t *template.Template, include func(...)) template.FuncMap {
    f := sprig.TxtFuncMap()           // Sprig 200+ 函数
    delete(f, "env")                  // Helm 删掉 sprig 里读环境变量的（防信息泄露/不确定性）
    delete(f, "expandenv")
    f["include"] = ...                // Helm 自加
    f["tpl"] = ...
    f["required"] = ...
    f["lookup"] = ...                 // 渲染时查集群（pkg/action 注入实现）
    return f
}
```

> **细节洞察**：Helm **故意删掉了 Sprig 的 `env`/`expandenv`**——防止模板读宿主环境变量，避免"同一 chart 在不同 CI 机器渲染出不同清单"（破坏可复现性）。这是 Helm 把"确定性渲染"当一等公民的体现，也是为什么 GitOps 能依赖 `helm template`。

## 6.4 主线三：Release 存储 `pkg/storage`

`pkg/storage.Storage` 封装 release 的 CRUD，底层是 `driver.Driver` 接口，三种实现：

```go
// pkg/storage/driver/driver.go
type Driver interface {
    Create(key string, rls *rspb.Release) error
    Update(key string, rls *rspb.Release) error
    Delete(key string) (*rspb.Release, error)
    Get(key string) (*rspb.Release, error)
    List(filter func(*rspb.Release) bool) ([]*rspb.Release, error)
    Query(labels map[string]string) ([]*rspb.Release, error)
}
```

- `SecretsDriver`（v3.1+ 默认）：每个 revision 一个 Secret，key = `sh.helm.release.v1.<name>.v<rev>`，value = gzip+base64 的 protobuf。
- `ConfigMapsDriver`：早期/兼容。
- `MemoryDriver`：测试/`helm template`。

`pkg/cli/envset.go` 根据配置（`HELM_DRIVER` 环境变量，默认 `secret`）选择 driver。

`Storage` 之上提供 `Create/Update/Get/History/Deployed/...` 等业务方法（`pkg/storage/storage.go`），`pkg/action` 调它。`--history-max` 的清理逻辑也在这里（`Storage` 在 Create 时检查 revision 数量、删最旧）。

## 6.5 清单排序与拆分 `pkg/releaseutil`

渲染出的是一个大文本（多文档 `---` 拆分），`pkg/releaseutil` 负责：

- `SplitManifests`：按 `---` 拆成单个文档。
- `SortByKind` / `kindSortOrder`：按资源类型排序（CRD → Namespace → ServiceAccount → RoleBinding → Secret → ConfigMap → Service → Deployment → HPA → Ingress → ...），保证依赖顺序。
- `Manifests` 分离 hook 与普通资源（按 `helm.sh/hook` 注解）。

这套排序是"为什么 `helm install` 不会先建 Deployment 再建它依赖的 ServiceAccount 报错"的根源——依赖顺序在客户端渲染后、apply 前就排好了。

## 6.6 依赖与 Chart 加载 `pkg/chart/loader`

`chartutil.Load`/`loader.Load`：从目录或 `.tgz` 加载 Chart 到内存 `chart.Chart` 结构（`Chart.yaml` → `chart.Metadata`，文件 → `chart.File`，templates → 遍历）。`pkg/action` 在 install/upgrade 前用它把 Chart 装进内存。

依赖解析：`pkg/chart` + `pkg/downloader`（`Manager.Update` 跑 `helm dependency update`，下载子 chart、写 `Chart.lock`）。安装时父 chart 的 `charts/` 里已含子 chart，渲染时父子各自 Render。

## 6.7 三条主线汇合：一次 install 的源码级全景

```
cmd/helm/install.go            # cobra 入口，解析参数
   │ action.NewInstall(cfg)
   ▼
pkg/action/install.go          # Install.Run(chart, vals)
   │ ├─ chartutil.ToRenderValues(...)      # 合并 values、构造上下文
   │ ├─ engine.Render(chrt, vals)          # 主线二：渲染
   │ ├─ releaseutil.SortByKind             # 主线：清单排序
   │ ├─ cfg.Releases.Create(rel)           # 主线三：存 pending Secret
   │ ├─ cfg.execHook(pre-install)
   │ └─ cfg.KubeClient.Create(target)      # 调 apiserver
   │      └─ pkg/kube/client.go Create/Update
   │           └─ strategicMergePatch / Patch  (upgrade 时：三方合并，主线一)
   ▼
   rel.SetStatus(deployed)
   cfg.Releases.Update(rel)     # 把 Secret 状态更新为 deployed
```

upgrade 把 `Create` 换成 `Update`（三方合并），rollback 把"渲染本次"换成"取目标 revision 的清单"，其余链路一致——这就是为什么四条命令的代码高度对称。

## 6.8 一个值得读的练习：自己跑 `helm template` 的渲染

`pkg/action/action.go` + `cmd/helm/template.go`：`helm template` 几乎是 `install.Run` 的"只渲染不 apply"版本——它走到 `engine.Render` 就返回，不碰 apiserver、不写 Secret。这正是 CI/GitOps 用它做"渲染 + diff + 审计"的基础，也让你能本地调试模板而无需集群。

```bash
helm template myrelease ./mychart -f values-prod.yaml > rendered.yaml   # 输出可审阅清单
helm template ... | kubectl apply --dry-run=server -f -                  # 服务端校验（不真创建）
```

## 本章小结

helm/helm 仓库分层清晰，抓三条主线即可贯通：**主线一（install/upgrade 调用链）**：`cmd/helm`（cobra）→ `pkg/action/install.go`/`upgrade.go`（业务动作）→ `pkg/kube`（与 apiserver 交互），其中 `pkg/kube.Client.Update` 用 `StrategicMergePatchType` 实现**三方合并**（old chart / live / new chart），是"Helm 升级为何保留手动改动"的代码根源。**主线二（模板渲染）**：`pkg/engine.Engine.Render` 注册 Sprig 函数（故意删掉 `env`/`expandenv` 保证确定性渲染）+ Helm 扩展（include/tpl/required/lookup），父子 chart 递归渲染、values 隔离。**主线三（Release 存储）**：`pkg/storage.Storage` + `driver.Driver`（Secret/ConfigMap/Memory，默认 Secret），每 revision 一个 gzip+base64 的 protobuf Secret，`--history-max` 在 Create 时清理。辅助：`pkg/releaseutil`（清单拆分 + 按资源类型排序保证依赖顺序、分离 hook）、`pkg/chart/loader`（Chart 加载）、`pkg/downloader`（依赖解析）。四条命令代码高度对称：install=Create、upgrade=Update(三方合并)、rollback=取旧清单走 upgrade、uninstall=逆序删除。`helm template` 是 install 的"只渲染不 apply"子集，是 CI/GitOps 的基石。从一条命令入口追到底，就能建立 Helm 全链路直觉。

**参考来源**

- [helm/helm 源码](https://github.com/helm/helm)
- [pkg/action（动作）](https://github.com/helm/helm/tree/main/pkg/action)
- [pkg/engine（模板引擎）](https://github.com/helm/helm/tree/main/pkg/engine)
- [pkg/kube（apiserver 交互与合并）](https://github.com/helm/helm/tree/main/pkg/kube)
- [pkg/storage（Release 存储）](https://github.com/helm/helm/tree/main/pkg/storage)
- [Sprig 函数源码](https://github.com/Masterminds/sprig)
