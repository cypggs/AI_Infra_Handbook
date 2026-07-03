# 4. Release 工作流程：install / upgrade / rollback / uninstall

> 一句话理解：本章把第 2、3 章的抽象落实成四条命令的完整时序——`helm install`（第一次部署）、`helm upgrade`（换 chart/values，走三方合并）、`helm rollback`（取旧 revision 清单重 apply）、`helm uninstall`（按逆序删资源 + 清 release Secret）；每条都对应一组明确的"渲染 → 合并 → 记录 → apply"步骤，以及一组典型故障模式。

## 4.1 前置：Release 的状态机

理解四条命令前，先记住 Release 的状态流转：

```
                   install 成功
        ┌──────────────────────────────┐
        ▼                              │
   [pending-install] ──失败──► [failed]│
        │ 成功                          │ (保留为历史)
        ▼                              ▼
   [deployed] ◄──── rollback ──── [deployed (旧rev→superseded)]
        │ upgrade                       
        ▼                              
   [pending-upgrade] ──失败──► [failed] 
        │ 成功                          
        ▼                              
   [deployed (rev+1)]  旧 rev → [superseded]
        │
   uninstall
        ▼
   [uninstalling] ──► [uninstalled]（Secret 也被删，除非 --keep-history）
```

状态：`pending-install`/`pending-upgrade`/`pending-rollback`（**进行中**，崩溃会卡在这）、`deployed`（最新成功）、`superseded`（被新版本取代的历史版本）、`failed`、`uninstalling`、`uninstalled`。

> **救援要点**：卡在 `pending-*` 的 release 不能直接再操作（Helm 会报错 "another operation in progress"），需要先 `helm rollback` 到上一个稳定版或手动修状态（第 8 章）。

## 4.2 `helm install` 完整时序

```
$ helm install myrelease mychart -n prod -f values-prod.yaml --set image.tag=v1.4.2 --wait --timeout 5m
```

步骤：

1. **参数解析 + kubeconfig 加载**：确定目标 namespace=prod、release name=myrelease，加载 kubeconfig（受你 RBAC 约束）。
2. **加载 Chart**：
   - 若 `mychart` 是本地目录 → 直接读 `Chart.yaml`/`values.yaml`/`templates/`。
   - 若是 repo/chart 形式 → 先在已 add 的 repo 的 `index.yaml` 里解析，`helm pull` 下来。
   - 若是 `oci://...` → 走 OCI 拉取。
   - **依赖解析**：若有 `dependencies`，确保 `charts/` 里有子 chart（否则报错让你先 `helm dependency update`）。
3. **合并 values**（优先级从低到高）：
   - 子 chart 的 `values.yaml`。
   - 父 chart 的 `values.yaml`（父对子的覆盖段）。
   - `-f values-prod.yaml`。
   - `--set image.tag=v1.4.2`。
4. **渲染模板**：对父 chart 和所有子 chart 的 `templates/` 跑 Go template，每个文件产出一个文档。Hook 资源按权重排序，普通资源按"CRD → Namespace → ServiceAccount → Role/Binding → Secret → ConfigMap → Service → Deployment → …"约定排序。
5. **渲染校验**：基本语法/必填校验；可用 `--dry-run` / `helm template` 只渲染不 apply。
6. **执行 `pre-install` Hook**：把 `helm.sh/hook: pre-install` 的资源（如建 namespace 的 Job）apply 并**等待完成**。
7. **写 Release Secret（revision 1，状态 pending-install）**：把"本次 chart + 合并后的 values + 渲染清单"编码进 `sh.helm.release.v1.myrelease.v1`。**先写 pending 再 apply**，保证崩溃可追溯。
8. **apply 主体资源**：通过 client-go 调 apiserver，按排序顺序创建（CRD 先于 CR、ServiceAccount 先于引用它的 Deployment……）。
9. **执行 `post-install` Hook**：主体 apply 后跑（如初始化 Job）。
10. **--wait 等待 ready**：若指定 `--wait`，阻塞直到所有 Deployment 副本 ready、Job 成功、PVC bound，或 `--timeout` 超时。
11. **更新 Release Secret**：状态 `pending-install → deployed`。
12. **打印 `NOTES.txt`**：渲染成功提示。

崩溃处理：任一步骤失败，release 状态置 `failed`（或卡 `pending-install`）。`--wait` 超时也会置 failed。失败后可用 `helm uninstall myrelease` 清理，或 `helm upgrade --reset-then-reuse-values` 重试。

## 4.3 `helm upgrade` 完整时序（核心：三方合并）

```
$ helm upgrade myrelease mychart -n prod -f values-prod.yaml --reset-values --atomic --wait
```

步骤（与 install 的差异用 ★ 标注）：

1–5. **参数/Chart/values/渲染**：同 install，但渲染出的是**新版本清单**（v3）。
6. ★ **读取上一版 release**：从 Secret 读 revision N（当前 deployed）的 chart、values、**渲染清单（v_prev）**。
7. **pre-upgrade Hook**。
8. ★ **写 Release Secret（revision N+1，状态 pending-upgrade）**。
9. ★ **三方合并 Patch**：对每个资源，用 ① v_prev 清单 ② 集群现状 ③ v3 清单 算出 patch，应用：
   - 资源在 v3 有、v_prev 有 → patch（保留集群里 chart 之外的改动）。
   - 资源在 v3 有、v_prev 无 → 创建（chart 新增的）。
   - 资源在 v3 无、v_prev 有 → 删除（chart 删掉的）。
   - 资源在 v3 无、v_prev 无（人工建的）→ 不动。
10. **post-upgrade Hook**。
11. **--wait ready / --atomic 回滚**：
    - `--atomic`：若 upgrade 失败或超时，**自动 rollback 到 N**（生产强烈推荐，避免半升级状态）。
12. ★ **更新两个 Secret**：revision N 状态 `deployed → superseded`；revision N+1 状态 `pending-upgrade → deployed`。

**`--reset-values` vs `--reuse-values`**（易混）：

| 选项 | 升级用的 values |
|---|---|
| 默认（都不加）= `--reset-values` | **只用本次命令行给的**（`-f`/`--set` + chart 默认），**丢弃**上次的 values |
| `--reuse-values` | **以上次 revision 的 values 为底**，再叠加本次命令行覆盖 |
| `--reset-then-reuse-values` | 先 reset 再 reuse（细节差异，少见） |

> **坑**：很多人 `helm upgrade myrelease mychart`（不带任何 `-f`/`--set`），以为"保持上次配置"。**错**——默认 `--reset-values`，会用 chart 的默认 values **覆盖**你上次用 `-f prod.yaml` 装的配置。生产升级**永远显式带 `-f values-prod.yaml`**，或用 `--reuse-values`。

## 4.4 `helm rollback` 完整时序

```
$ helm rollback myrelease 3 -n prod --wait
```

步骤：

1. **读取目标 revision**：从 Secret `sh.helm.release.v1.myrelease.v3` 取出那一版的**渲染清单 + chart + values**。
2. **pre-rollback Hook**。
3. **写新 Secret（revision N+1，状态 pending-rollback）**：内容是 revision 3 的清单。
4. ★ **三方合并 Patch**：用 ① 当前 deployed（rev N）清单 ② 集群现状 ③ 目标 revision 3 的清单，算出 patch 应用。本质是"用旧清单做一次 upgrade"——它**不是简单地删除/重建**，而是把集群状态往 revision 3 的清单收敛，**保留你 chart 之外的手动改动**（除非那些改动在 revision 3 里不存在）。
5. **post-rollback Hook**。
6. **--wait ready**。
7. **更新 Secret**：rev N → superseded，rev N+1（内容同 rev3）→ deployed。

> **要点**：rollback 会**新增一个 revision**（不是"指针回到 3"），`helm history` 里你会看到 `rev5 deployed (rollback to 3)`。原 revision 3 仍是 `superseded`。这点常被误解。

## 4.5 `helm uninstall` 完整时序

```
$ helm uninstall myrelease -n prod          # 或 --keep-history
```

步骤：

1. **读当前 deployed revision 的清单**：拿到 Helm 管理的所有资源列表。
2. **pre-delete Hook**。
3. **按逆序删除资源**：先删 workloads（Deployment/StatefulSet）再删依赖（Service/ConfigMap）、最后 ServiceAccount/Namespace；带 `helm.sh/resource-policy: keep` 的**跳过**（保留数据/资源）。
4. **等待删除完成**（默认删除是异步的，Helm 会等 `finalizer` 处理完）。
5. **post-delete Hook**。
6. **删 Release Secret**：所有 revision 的 Secret 都删（`sh.helm.release.v1.myrelease.v*`）。
7. 加 `--keep-history` 则**保留** release Secret（`helm list` 仍可见，状态 uninstalled），便于审计；不加则彻底清。

> **常见坑**：`kubectl delete` 删了 Helm 装的资源，但没 `helm uninstall` → release Secret 还在，`helm list` 仍显示 deployed，下次 upgrade 会试图 patch 已不存在的资源。正解：始终用 `helm uninstall` 卸载，或先 uninstall 再清残留。

## 4.6 把四条命令的差异对齐成一张表

| 维度 | install | upgrade | rollback | uninstall |
|---|---|---|---|---|
| 目标 | 首次部署 | 换 chart/values | 回到历史 revision | 移除 |
| revision 变化 | 创 1 | N → N+1 | N → N+1（内容=目标版） | 删除所有 |
| 用到的清单 | 本次渲染 | 本次渲染（三方合并） | **历史 revision 的清单** | 当前 deployed 清单（用于删） |
| 人工改动 | 无（新建） | **保留**（三方合并） | 保留 | 删除（Helm 管的） |
| 失败状态 | failed/pending-install | failed/pending-upgrade | failed/pending-rollback | 仍可能残留 |
| `--atomic`（自动回滚） | N/A | ✅ 强烈建议 | N/A | N/A |
| `--wait` 等待 ready | 可选 | 推荐 | 推荐 | 可选 |

## 4.7 典型故障与定位

| 症状 | 原因 | 处理 |
|---|---|---|
| upgrade 后手动 scale 的副本被改回 | 用了 `--reuse-values` 且新 values 没带副本；或二方合并工具 | 三方合并本应保留；确认是 Helm v3 而非 `kubectl apply` |
| release 卡 `pending-upgrade` | upgrade 中途崩溃（CI 被杀、网络断） | `helm rollback myrelease <last-good>`；或手动改 Secret annotation（第 8 章） |
| `helm upgrade` 报 "has been updated" 不生效 | 默认 `--reset-values` 丢了配置 | 显式带 `-f values-prod.yaml` 或 `--reuse-values` |
| uninstall 后 PVC 被删 | Chart 没给 PVC 加 `helm.sh/resource-policy: keep` | Chart 里加该注解；或用 StatefulSet volumeClaimTemplates + retention policy |
| 渲染出的清单有 `<no value>` 或空行导致 YAML 解析失败 | 模板没做空白修剪、`--set` 给了空值 | 用 <code v-pre>{{- -}}</code> 修剪、`required` 强制必填 |
| Hook Job 卡住导致 install 永久 pending | Hook 没 `hook-delete-policy`、Job 失败重试 | 加 `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded` |
| `lookup` 渲染结果在 GitOps 与本地不一致 | `lookup` 依赖集群实时状态 | 慎用 lookup，GitOps 场景禁用（第 5 章） |

## 本章小结

Helm 的四条核心命令各有清晰时序：`install`（加载→合并 values→渲染→pre-install hook→写 pending Secret→apply→post hook→wait→deployed）、`upgrade`（读上一版清单→三方合并 Patch→apply→`--atomic` 失败自动回滚→旧版 superseded / 新版 deployed）、`rollback`（取目标 revision 清单，本质上是用旧清单做一次 upgrade，会新增 revision 而非"指针回拨"）、`uninstall`（按逆序删资源，跳过 `resource-policy: keep`，删 release Secret）。核心机制是**三方合并 Patch**——升级/回滚都保留 chart 之外的手动改动。关键易错点：默认 `--reset-values` 会覆盖上次配置（生产永远显式带 `-f`）、`--atomic`+`--wait` 是生产升级标配、rollback 会新增 revision、卡 `pending-*` 要先 rollback 救援。把这四条命令的时序和故障模式记牢，日常发布就稳了。

**参考来源**

- [helm install](https://helm.sh/zh/docs/helm/helm_install/) / [helm upgrade](https://helm.sh/zh/docs/helm/helm_upgrade/) / [helm rollback](https://helm.sh/zh/docs/helm/helm_rollback/) / [helm uninstall](https://helm.sh/zh/docs/helm/helm_uninstall/)
- [三方合并（v3 upgrade）](https://helm.sh/zh/docs/intro/using_helm/)
- [Hook 生命周期](https://helm.sh/zh/docs/charts_hooks/)
- [resource-policy 注解](https://helm.sh/zh/docs/howto/charts_tips_and_tricks/#tell-helm-not-to-uninstall-a-resource)
