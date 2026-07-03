# 3. 架构设计：客户端渲染、Release 存储、三方合并

> 一句话理解：Helm v3 的架构极其简单——**它就是一个客户端 CLI**：加载 Chart → 合并 values → 本地渲染出 YAML → 用你的 kubeconfig 调 kube-apiserver（受 RBAC 约束）→ 把结果存成 namespace 内的 Secret 作为 Release。没有常驻服务端、没有自己的权限。它的"架构"难点不在组件，而在**三方合并 Patch**（升级时怎么算"该改哪些字段"）和 **Release 存储模型**这两件事。

## 3.1 一句话架构与全景图

```
┌──────────────────────────────────────────────────────────────────┐
│  你的机器 / CI Runner                                            │
│                                                                  │
│   helm CLI                                                       │
│   ┌──────────────────────────────────────────────────────┐       │
│   │ 1. 解析参数 (install/upgrade/rollback/...)            │       │
│   │ 2. 加载 Chart（本地目录 / 从 repo pull / 从 OCI 拉）   │       │
│   │ 3. 合并 values (Chart.yaml deps + values.yaml         │       │
│   │      + -f 覆盖 + --set)                               │       │
│   │ 4. 引擎渲染 (pkg/engine: Go template + Sprig)         │       │
│   │      → 产出一组 K8s 清单 (manifests)                  │       │
│   │ 5. 校验 (kubeval/lint/渲染后 schema)                  │       │
│   │ 6. 计算变更 (三方合并 Patch / rollback 直接取旧版)     │       │
│   │ 7. 通过 kubeconfig 调 kube-apiserver (apply)          │       │
│   │ 8. 把本次 release 存成 Secret (Release 存储)          │       │
│   │ 9. 渲染并打印 NOTES.txt                               │       │
│   └──────────────────────────────────────────────────────┘       │
│            │                                                     │
└────────────┼─────────────────────────────────────────────────────┘
             │  HTTPS (用 kubeconfig 里的证书/token，受 K8s RBAC 约束)
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Kubernetes 集群                                                  │
│   kube-apiserver ── etcd                                         │
│      │                                                            │
│      └──> <release 命名空间>                                      │
│             ├── Secret: sh.helm.release.v1.<name>.v1  (revision1)│
│             ├── Secret: sh.helm.release.v1.<name>.v2  (revision2)│
│             └── 你 Chart 部署的真实资源 (Deployment/Service/...)  │
└──────────────────────────────────────────────────────────────────┘
```

> **关键认知**：右半边（kube-apiserver + etcd + 你部署的资源）**不属于 Helm**，它是 Kubernetes。Helm 只是一个写得很完善的"客户端渲染器 + apply 自动化器 + 版本记录器"。这也直接回答了第 1 章的疑问——"Helm 做的事 kubectl 都能做"。

## 3.2 为什么删掉 Tiller（v2 → v3 的核心架构决策）

回顾第 1 章：v2 时有一个集群内的服务端 **Tiller**，Helm CLI 把 Chart 发给它，它去调 apiserver。这个设计的根本问题是**安全**：

```
v2（有 Tiller）:
  CI 机器 --[无鉴权 gRPC]--> Tiller (cluster-admin) --[cluster-admin]--> apiserver
                                ↑
                  任何能连到 Tiller 端口的人 = cluster-admin
```

v3 的方案是**彻底删掉服务端**，让 CLI 直接用调用者的 kubeconfig：

```
v3（无 Tiller）:
  CI 机器 --[你的 kubeconfig]--> apiserver (按你的 RBAC)
  （Helm CLI 本地完成渲染）
```

后果（全是优点）：

1. **鉴权回归 K8s RBAC**：你能 `kubectl apply` 什么，`helm install` 就能做什么；你不能的，Helm 也不能。RBAC 成为唯一鉴权点，审计清晰。
2. **无集群内高权限后门**：没有 Tiller = 没有 cluster-admin 的常驻进程可被打。
3. **Release 作用域 = namespace**：v2 的 release 全集群共享（名字全集群唯一），v3 改为**每个 namespace 独立**（`helm install -n prod myapp` 的 `myapp` 只在 prod 内唯一），天然支持多租户/多环境隔离。
4. **多 Tiller 冲突消失**：v2 时每个团队可能装自己的 Tiller，互相打架；v3 没这问题。

代价：v2 里"Tiller 帮无权限的 CI 部署"那个**初衷**没了——v3 必须给 CI 一个有限权限的 kubeconfig（RBAC 绑定到某 namespace、能操作某些资源），这恰恰是更安全的做法，所以业界一致认为 v3 的取舍正确。

## 3.3 Release 存储模型：从 ConfigMap 到 Secret

Release 的元数据（chart、values、渲染清单、状态）必须持久化，否则 `helm history`/`rollback` 无从谈起。存储的演进：

| 版本 | 存储对象 | 说明 |
|---|---|---|
| Helm v2 | `kube-system` 的 **ConfigMap** | 全集群一个命名空间，名字 `myapp.v1` |
| Helm v3.0 | 所在 namespace 的 **ConfigMap** | 改 namespace 内 |
| **Helm v3.1+（默认）** | 所在 namespace 的 **Secret** | 改用 Secret，因为渲染出的清单里**可能含 Secret 资源**（含敏感数据），存进 ConfigMap（明文 etcd）有泄露风险 |

Secret 的名字：`sh.helm.release.v1.<release-name>.v<revision>`，类型 `helm.sh/release.v1`。其 `data.release` 字段是 gzip + base64 编码的 release 对象 protobuf。

**实操含义**：

- `helm list -n prod` / `helm history myapp -n prod` = 读这些 Secret。
- 一个 release 卡在 `pending-upgrade`（升级中途崩溃），往往是因为那个 `v<N>` Secret 写了但 apply 没完——救援方式见第 8 章。
- **删除 release 资源但忘卸载**：如果你手动 `kubectl delete` 了 Helm 装的资源，Helm 的 Secret 还在，`helm list` 仍显示它；正确的卸载是 `helm uninstall myapp`（会同时清资源 + Secret，除非标了 `helm.sh/resource-policy: keep`）。
- **etcd 容量**：大量 release（尤其每版清单很大，如几百个对象的平台 chart）会累积大量 Secret。要配 `helm upgrade --history-max` 或定期 `helm uninstall`/`helm history` 清理旧 revision。

> **辨析**：很多初学者以为"Release 是 K8s 里的某种自定义资源（CR）"。**不是**。Helm 没有定义任何 CRD，Release 就是普通 Secret。Helm 不需要在集群里"安装"自己就能工作——这也是 v3 "无服务端"哲学的体现。

## 3.4 三方合并 Patch：升级的核心算法

这是 Helm v3 最容易被忽略、却最该理解的设计。问题是：**升级时，Helm 怎么算出"该改哪些字段"？**

考虑这个场景：

1. **revision 1**：你装了 chart，渲染出 Deployment 的 `replicas: 2`。
2. **人工干预**：业务做大促，你 `kubectl scale deployment x --replicas=10` 把它扩到 10。
3. **revision 2（upgrade）**：你升级了 chart（比如换了镜像），但 chart 里 `replicas` 还是 2。**这时集群里该是多少？**

- 如果 Helm 用"二方合并"（只用新 chart 覆盖集群现状），它会把 replicas 强行改回 2，**把你手动扩的 10 覆盖掉**——这是灾难。
- Helm v3 用**三方合并（three-way merge / strategic merge patch 的扩展）**：它同时参考 ① 上一版（revision 1）渲染出的清单 ② 当前集群实际状态 ③ 这次（revision 2）渲染出的清单，算出"从①到②期间人工改了什么"，并**保留这些人工改动**，只应用"从①到③ chart 本身的变化"。

具体到上例：

- ①（rev1 清单）：replicas=2
- ②（集群现状）：replicas=10（人工扩了）
- ③（rev2 清单）：replicas=2（chart 没改这一项）

三方合并发现"chart 这一项（replicas）从 rev1 到 rev2 没变，但集群里被人工改成了 10"——于是**保留 10**，只应用 chart 真正变化的（镜像）。**你手动扩容没被覆盖。**

对比二方合并（v2 的某些场景 / Kustomize 的简单 apply）：

| 情况 | 二方合并结果 | 三方合并结果（Helm v3） |
|---|---|---|
| chart 改了某字段 | 应用新值 | 应用新值（一致） |
| chart 没改、人工改了 | **覆盖人工改动（坏）** | **保留人工改动（好）** |
| chart 删了某资源 | 删除 | 删除 |
| 人工删了 chart 没改的资源 | 重新创建 | **不重建**（保持人工删除） |

> **一句话记住**：三方合并 = "Helm 只动'chart 本身在这个 release 之间改过的字段'，对你（chart 之外）的手动改动保持敬畏、尽量不动"。这是 Helm 比"裸 apply"在升级安全性上的根本优势。**但注意边界**：它只对 Helm **管理的资源**生效；你手动新建的资源、或 Helm 不管的字段（如 Pod 的 spec.containers 里 Helm 渲染时没写死的注解），不受保护。

实现上，Helm v3 用 `pkg/kube` 调用 client-go，对每个资源用 K8s 的 **strategic-merge-patch**（有 schema 的结构化 patch，知道 `containers` 是 list、用 name 当 key）或 **JSON merge patch**（无 schema 时退化）来做三方合并。

## 3.5 渲染引擎：Go template + Sprig + Helm 扩展

渲染发生在客户端 `pkg/engine`，三层叠加：

1. **Go `text/template`**：基础语法（<code v-pre>{{ }}</code>、`if`/`range`/`with`、`define`/`template`、管道）。
2. **Sprig**：200+ 实用函数（字符串/数值/日期/编码/列表/字典/加密）。
3. **Helm 自加的函数/对象**：
   - `include`/`tpl`（把字符串当模板再渲染）。
   - `lookup`（**渲染时实时查集群**，见第 5 章——延迟绑定，慎用，会让渲染依赖集群状态、不利于 GitOps 纯净）。
   - `.Release`/`.Chart`/`.Values`/`.Files`/`.Capabilities`/`.Template` 上下文对象。
   - `required`（值为空就报错中止，强制必填）。

引擎把 `templates/` 下每个文件（除 `_` 开头的 helper 和 NOTES.txt/tests 特殊处理）渲染成一个文档，再把多个文档按"hook 权重 + 资源类型顺序（CRD → Namespace → ServiceAccount → …）"排序，得到最终的清单列表，供后续 apply。

## 3.6 与 kube-apiserver 的交互（`pkg/kube`）

Helm 自己**不直接操作 etcd**，而是通过 client-go 调 apiserver。它复用了 K8s 的"声明式 apply"语义：

- `helm install`：把渲染出的所有清单**创建**到集群。
- `helm upgrade`：对每个资源做**三方合并 patch**。
- `helm rollback`：取目标 revision 的清单，再走一遍 upgrade 路径（本质是"用旧版清单做一次三方合并"）。
- `helm uninstall`：删除 Helm 管理的所有资源（按逆序：先删 workloads 后删依赖），删完再删 release Secret。标了注解 `helm.sh/resource-policy: keep` 的资源**不被删**（常用于 PVC——卸载应用但保留数据）。

> **等待 ready**：`helm install --wait` 会让 Helm 在 apply 后**阻塞等待**所有资源到达 ready（Deployment 副本数达标、Job 完成、PVC bound），超时（`--timeout`）则标记 release failed。不加 `--wait` 则 apply 完立即返回（资源还在异步创建）。生产 CI/CD 几乎总是带 `--wait --timeout 5m`。

## 3.7 Hook：在声明式 apply 里塞"一次性动作"

K8s 是声明式 + 最终一致，但有些事是**一次性、有时序的**：装 DB 前先建 namespace、装应用后跑一次 DB migration Job、升级前备份。Helm 用 **Hook** 解决：给资源加注解 `helm.sh/hook: pre-install`（或 `post-install`/`pre-upgrade`/`post-upgrade`/`pre-rollback`/`post-rollback`/`test` 等），Helm 会在**对应生命周期阶段**优先调度它，且：

- `pre-*` hook 在主体资源 apply **之前**跑。
- `post-*` hook 在主体资源 **之后**跑。
- Hook 资源默认带 `helm.sh/hook-delete-policy`（hook 完成后删除 Job/Pod），避免堆积。
- `helm.sh/hook-weight` 控制同阶段多个 hook 的顺序（数字小的先）。

> **Hook vs Operator**：Hook 是"一次性的、绑定在 install/upgrade 时机"的；Operator 是"长期运行的、持续观察集群"的。需要"装好后跑一次迁移"用 Hook；需要"持续监控 Pod 状态并自愈"用 Operator。

## 3.8 Library Chart 与 post-renderer：扩展点

- **Library Chart**（`type: library`）：只提供命名模板，不产出资源。被 `dependencies` 引入后，父 chart 用 `include "libchart.helper" .` 复用其模板。解决"模板复用"（label/name 生成、公共 ConfigMap 片段）。
- **post-renderer**（`helm install --post-renderer ./my-renderer`）：Helm 渲染完清单后、apply 之前，**把全部清单文本经一个外部可执行文件处理一遍**再 apply。是"逃生舱"：当模板引擎做不到的需求（注入 sidecar、套 Kustomize patch、注入 OPA/Gatekeeper 注解、按集群动态改）可以在这里做。常用组合：`--post-renderer kustomize`。

## 本章小结

Helm v3 的架构核心是"**无服务端、纯客户端**"：CLI 本地完成"加载 Chart → 合并 values → Go template 渲染 → 三方合并 Patch → 通过 kubeconfig 调 kube-apiserver → 把 release 存成 namespace 内 Secret"。删掉 v2 的 Tiller 让鉴权回归 K8s RBAC（受调用者权限约束）、消除了集群内高权限后门、release 作用域天然落到 namespace（支持多租户）。Release 存储从 ConfigMap（v2/v3.0）改为 **Secret（v3.1+ 默认）** 以防渲染清单里的敏感数据明文进 etcd，名字 `sh.helm.release.v1.<name>.v<rev>`，是 Helm 的 undo log。架构上最该理解的是**三方合并 Patch**：升级时同时参考"上一版清单 + 集群现状 + 本次清单"，保留 chart 之外的手动改动，只应用 chart 自身变化——这是 Helm 升级安全性的根本。此外，渲染引擎（Go template + Sprig + Helm 扩展如 `lookup`/`required`）、Hook（声明式 apply 里塞一次性时序动作）、Library Chart（模板复用）、post-renderer（渲染后逃生舱）是四个关键扩展点。理解了"客户端渲染 + Secret 存储 + 三方合并"，Helm 的架构就通透了。

**参考来源**

- [Helm 架构](https://helm.sh/zh/docs/topics/architecture/)
- [三方合并与升级](https://helm.sh/zh/docs/intro/using_helm/#help-options)
- [Helm v3 FAQ：删除 Tiller](https://helm.sh/zh/docs/faq/#removal-of-tiller)
- [Release 存储（Secret）](https://helm.sh/zh/docs/topics/v2_v3_migration/)
- [Hook 文档](https://helm.sh/zh/docs/charts_hooks/)
