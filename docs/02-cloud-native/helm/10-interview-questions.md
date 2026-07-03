# 10. 面试题精讲：从概念到生产

> 一句话理解：本章用 24 道题（初级 8、中级 9、高级 7）覆盖 Helm 的概念、机制、实现与生产落地——每题不只给"答案"，更给"为什么这样设计"的推理路径，帮你把前 9 章的知识点连成可应试、可深聊的体系。

## 10.1 初级：概念与基本用法

**Q1. 一句话解释 Helm 是什么，它解决了裸 YAML 的什么问题？**

Helm 是 Kubernetes 的包管理器，把"一组 K8s 资源 + 可配置参数"打包成 Chart，提供版本化、可复用、一键部署的能力。它解决裸 YAML 的四个问题：环境差异靠复制、升级无版本、依赖手动按序、复用靠 sed（详见第 1 章"裸 YAML 四宗罪"）。一句话：**它之于 K8s，相当于 apt/yum 之于 Linux**。

**Q2. Chart、Release、Repository 三个概念的区别？**

- **Chart**：一个**蓝图/模板包**（含模板 + 默认 values），不可变，类似 `.deb` 包。
- **Release**：Chart 在集群里的**一次具体部署实例**（有名字、命名空间、revision 历史），类似"已安装的软件"。
- **Repository**：存放和分发 Chart 的**仓库**（HTTP index 或 OCI registry），类似 apt 源。

一个 Chart 可以有多个 Release（同一应用部署到 dev/staging/prod 是三个 release）。

**Q3. `Chart.yaml` 里 `version`、`appVersion`、`apiVersion` 各是什么？**

- `version`：**chart 自己的版本**（SemVer），改 chart 就改它。
- `appVersion`：chart 打包的**应用版本**（如 `0.7.0`），只是元数据，不强制参与渲染（除非模板里用 `.Chart.AppVersion`）。
- `apiVersion`：chart 格式版本（`v2`），v1 是 Helm v2 遗留，新 chart 一律 `v2`。

易错点：改了应用代码但忘了 bump `version`，OCI push 会被拒（版本已存在）。

**Q4. values 的覆盖优先级是什么？**

从低到高：**子 chart 默认 values < 父 chart values < `-f` 文件 < `--set` < `--set-string`**。合并规则：map 递归合并，**list 整体替换**（不是按下标合并）。`global` 段在父子 chart 间共享（详见第 2 章 2.2）。

**Q5. `helm upgrade` 和 `helm install` 有什么区别？什么情况下用 `--install`？**

`install` 创建新 release（revision 1）；`upgrade` 在已有 release 上升级（revision +1），走三方合并。`helm upgrade --install`（`-i`）是幂等写法——不存在则 install，存在则 upgrade，CI/CD 里几乎都用这个。

**Q6. <code v-pre>{{- </code> 和 <code v-pre> -}}</code> 是什么意思？为什么模板里到处都是？**

<code v-pre>{{-</code> 修剪动作**左边**的空白（包括前一行末尾换行），<code v-pre>-}}</code> 修剪**右边**空白。Go template 的动作标记本身会留下空行，不修剪会渲染出大量空行，甚至破坏 YAML 缩进。规则：**行首的动作加 <code v-pre>{{-</code>，行尾的动作加 <code v-pre>-}}</code>**（详见第 2 章 2.3）。

**Q7. `helm rollback` 会让 revision 号变小吗？**

**不会，反而变大**。rollback 取出目标 revision 的清单，**当作一次新 upgrade 执行**（同样走三方合并），新建一个 revision。所以 revision 号永远单调递增。好处：rollback 也是可审计、可再回滚的操作，历史完整保留。

**Q8. 一个 release 有哪些状态？**

`pending-install` / `pending-upgrade` / `pending-rollback`（进行中）、`deployed`（成功）、`superseded`（被新版本取代）、`failed`（失败）、`uninstalling` / `uninstalled`（卸载中/已卸载）。`helm list` 默认只显示 `deployed` 和 `failed`。

## 10.2 中级：机制与原理

**Q9. Helm v2 的 Tiller 为什么被移除？v3 怎么解决的？**

Tiller 是 v2 的服务端组件，运行在集群里且默认高权限（cluster-admin），有三个问题：①**权限过大**，任何能连 Tiller 的人都能操作全集群；②**多租户隔离难**，Tiller 是单点；③**攻击面大**，服务端常驻进程需打补丁。

v3 的解法：**移除 Tiller，完全客户端渲染**。Helm CLI 用调用者的 kubeconfig 直接和 apiserver 通信，权限完全由 kubeconfig 的 RBAC 决定——谁部署，就用谁的权限。Release 存储从集群级的 ConfigMap 改成**命名空间内的 Secret**（含敏感信息，且隔离）。这是 v3 最大的架构进步（详见第 3 章 3.2）。

**Q10. 为什么 Release 用 Secret 存，而不是 ConfigMap？**

v2 用 ConfigMap，v3 改用 Secret，原因：①values 里常有敏感信息（密码、token），ConfigMap 明文不安全；②Secret 的访问受 RBAC 更严格控制。Secret 名字固定：`sh.helm.release.v1.<release>.v<revision>`，type `helm.sh/release.v1`。内容是 gzip + base64 + protobuf 编码的整个 Release 对象（含渲染后的清单）。每个 revision 一个 Secret，组成"undo log"。

**Q11. ★ 三方合并是什么？为什么 Helm 要三方而不是两方？请举例。**

`kubectl apply` 是两方合并（live vs new）：用新清单覆盖集群。问题是**会冲掉 chart 之外的手动改动**。比如人工 `kubectl scale` 把副本从 2 改到 10，下次 `apply`（chart 里还是 2）会把 10 冲回 2。

Helm 三方合并同时参考 **old**（上一版 chart 渲染的）、**live**（集群现状）、**new**（本次 chart 渲染的）：

- chart 在 old→new 之间**没改**的字段：保留 live（人工改动）。
- chart **改了**的字段：用 new。
- chart **删除**的字段：若 live 被人工改过则保留，否则删除。

举例（第 7 章场景 3）：人工扩容 replicas 2→10，`helm upgrade` 只换镜像（chart 的 replicas 没变），三方合并保留 replicas=10。这就是 Helm 相比裸 apply 的根本安全优势（详见第 3.4 节）。

**Q12. Helm 是怎么实现三方合并的？list 怎么合并？**

Helm 用 K8s 的 **strategic-merge-patch**（不是普通 JSON merge）。对 list，它按每个 list 项的 **merge key**（如容器的 `name`、env 的 `name`）合并——同名项合并，不同名项并列。比如 Deployment 的 `containers` 列表，按容器名合并；`env` 列表按环境变量名合并。对没有 merge key 的 list，退化为整体替换。

> 这也是为什么 mini-demo（第 7 章）简化成 list 整体替换——足够演示"replicas 不被覆盖"的语义，但真实 Helm 的 list 合并更精细。

**Q13. `--reset-values` 和 `--reuse-values` 的区别？什么时候用？**

`upgrade` 默认 `--reset-values`：**丢弃上次部署时的 `--set`/`-f` 覆盖**，只保留 chart 默认 values + 本次传入的覆盖。`--reuse-values`：**保留上次部署的全部 values**，本次的覆盖叠加在上面。

场景：CI 部署用默认（reset，每次完整传 values）；手动微调一个字段不重传全部用 reuse。易错：用了 reuse 又传了新 values，行为是"保留旧的 + 叠加新的"，可能与预期不符。

**Q14. Hook 是什么？和普通资源有什么区别？**

Hook 是带 `helm.sh/hook` 注解的资源，在 release 生命周期的特定时机执行（`pre-install`/`post-install`/`pre-upgrade`/`pre-rollback`/`test` 等），而不随 release 常驻。典型用途：`pre-install` 跑数据库迁移、`post-install` 发通知、`test` 做健康检查。Hook 资源**不属于 release**，`helm uninstall` 不会自动删（需配 `hook-delete-policy`）。

**Q15. `helm.sh/resource-policy: keep` 解决什么问题？**

`uninstall` 时默认删除 release 的所有资源。但有些资源不可重建（PVC 里的模型权重、已签发的 TLS 证书、CRD），加这个注解后 `uninstall` 会**跳过删除**它们。注意：这会让资源永久残留，需手动清理。对 AI 推理服务的 PVC 权重和 RayCluster CRD 几乎必加（详见第 7 章场景 7、第 9 章）。

**Q16. `helm template` 和 `helm install --dry-run` 有什么区别？**

- `helm template`：**纯离线渲染**，不连集群，不读 Release 上下文里的历史，输出清单到 stdout。CI diff 用。
- `install --dry-run`：**连集群**做一次模拟（验证 values、检查资源是否冲突），但不真正 apply。`lookup` 函数在这种模式下能查到集群。

区别在于是否连集群。`helm template` 在 CI 里更可重现（不依赖集群状态）。

**Q17. OCI registry 相比传统 HTTP chart 仓库有什么优势？**

传统 chart 仓库是个静态 HTTP 服务 + `index.yaml`， OCI（2022 GA）把 chart 当成普通镜像存：

- **统一基础设施**：和容器镜像用同一套 registry（Harbor/ACR/ECR）、同一套权限、同一套扫描。
- **不可变 + 签名**：OCI digest 不可变，配合 cosign 签名验证来源（`helm install --verify`）。
- **更快的分层拉取**、更好的镜像缓存命中。

现在官方推荐用 OCI（`helm push/pull oci://...`），传统 HTTP 仓库逐步淡出。

## 10.3 高级：实现与生产落地

**Q18. 描述 `helm install` 从命令行到集群的完整链路。**

1. CLI（`cmd/helm/install.go`）解析参数，构造 `action.Install`。
2. 合并 values（chart 默认 + `-f` + `--set`，按优先级）。
3. 渲染：`pkg/engine` 对每个模板执行 Go template + Sprig，注入 `.Values`/`.Release`/`.Chart` 上下文，产出多份 YAML 清单。
4. **先写 `pending-install` Secret**（含渲染清单）到目标 namespace。
5. 执行 pre-install hook。
6. `pkg/kube` 把清单按依赖排序（先 CRD/NS，后 workload，最后 Service/Ingress），调 apiserver 创建。
7. 若 `--wait`，等待所有资源 ready。
8. 成功→Secret 状态改 `deployed`；失败→改 `failed`，若 `--atomic` 则回滚已创建资源。

**Q19. 如果 `helm upgrade` 在 apply 过程中崩溃了（比如网络断了），会发生什么？集群会处于什么状态？怎么恢复？**

崩溃发生时：`pending-upgrade` Secret 已经写好（步骤 4 在 apply 之前），但 apply 只完成了一部分。集群处于**半升级状态**：部分资源是新版、部分还是旧版。Release 历史里有旧版（`deployed`/`superseded`）和新版（`pending-upgrade`）。

恢复：`helm list` 会显示这条 `pending-upgrade` 的 release（带 `--all` 看更全）。`helm rollback <release> <旧revision>` 把清单回退到旧版（注意 rollback 会新建一个 revision，三方合并尽量保留已 apply 的新版字段中合法的部分）。生产预防：用 `--atomic`，失败自动回滚；用 GitOps，控制器会检测漂移并自愈。

**Q20. 三方合并什么时候会"失败"（产生非预期结果）？如何避免？**

几种典型失效：

1. **chart 重复声明了控制器管理的字段**：如开了 HPA 还在 chart 写 `replicaCount`，三方合并因"chart 改了"误判。避免：开 HPA 就不写副本数。
2. **list 缺 merge key**：env 列表没加 `name`，strategic-merge 退化成整体替换，丢字段。避免：给 list 项加稳定 key。
3. **`lookup` 引入隐式状态**：渲染结果依赖集群，`helm diff` 失真。避免：不用 `lookup`。
4. **用 latest tag**：old.tag==new.tag=="latest"，Helm 判定"镜像没变"而保留旧的 live 镜像。避免：钉死版本。

**Q21. Helm 在 GitOps（Argo CD/Flux）下的行为有什么特别注意点？**

GitOps 控制器频繁 sync（`helm template` + apply），三方合并的价值被放大（不冲掉 HPA 弹性值），但也带来：

1. **`selfHeal` 与三方合并的交互**：控制器删掉 chart 移除的字段、保留人工未改的——要确保"该删的"在 chart 里真的删了。
2. **不要两套真相源**：GitOps 下别再手动 `kubectl scale` 或 `helm upgrade`，否则 sync 把手改冲掉（这正是设计意图，但常被误认为 bug）。
3. **`lookup` 在 GitOps 下更危险**：控制器的 dry-run 模式 lookup 行为可能和 install 不同，导致渲染不一致。
4. **release 名固定**：GitOps 应用名和 Helm release 名要对齐，否则 `helm list` 与 Argo CD 视图不一致。

**Q22. 如何设计一个给全公司 20 个团队复用的 AI 推理服务 chart？**

关键设计点：

- **参数化而非复制**：把团队差异全部抽到 values（镜像、模型、GPU 数、域名、配额），chart 模板一份。
- **`values.schema.json`**：强制校验 `tensorParallelSize` ∈ {1,2,4,8}、GPU 数与并行度匹配、模型名格式。
- **分层 values**：基线 + `values/<team>.yaml`，团队只写差异。
- **External Secrets**：每个团队的 HF token / DB 密码走 ESO，不进 chart。
- **Library Chart 抽公共逻辑**：把 fullname/labels/资源配额模板抽成 library chart，被 20 个 wrapper chart 依赖。
- **OCI + cosign**：chart 推私有 OCI 仓库并签名，团队 `helm install --verify`。
- **`helm test`**：chart 内置推理冒烟测试，确保模型真加载。
- **GitOps 部署**：每个团队一个 Argo CD Application，values 在各团队的 Git 仓库。

**Q23. Helm vs Kustomize，你的团队该怎么选？**

决策维度：

- 有**参数化和条件渲染**需求（多环境、可选组件）→ Helm。
- 只是**给上游清单打 patch**（加 label、改 image）→ Kustomize。
- 需要**版本化分发**（社区/跨团队复用）→ Helm。
- 团队**抗拒模板语法**、追求纯声明 → Kustomize。

AI 平台多数场景（推理服务、Ray、配额）参数多、有条件分支，**Helm 更合适**。关键是**别混用**——同一套资源既 Helm 又 Kustomize patch 会让变更追溯失效。

**Q24. 如何排查"chart 改了某字段但升级后集群没生效"？**

排查路径：

1. `helm get manifest <release> --revision <新版>`：看 Helm **渲染出来**的清单，确认改动确实在模板里。
2. `kubectl get <资源> -o yaml`：看集群**实际状态**。
3. 对比两者：若渲染清单有但集群没有 → 三方合并把它当"chart 没改"保留了旧值（检查 old 里这个字段是不是其实没变），或被 `lookup`/post-renderer 改了。
4. `helm diff revision <release> <旧版> <新版>`（helm-diff 插件）：直接看两版的渲染差异。
5. 若是 list 字段部分丢失 → 检查是否缺 merge key（strategic-merge 退化成整体替换）。
6. 检查 `helm history` 和 `get values --revision`，确认升级真的用了你以为的 values（`--reuse-values` 陷阱）。

## 本章小结

- **初级**抓概念边界：Chart/Release/Repository、version/appVersion/apiVersion、values 优先级、状态机。
- **中级**抓核心机制：Tiller 为何移除、Secret 存储、**三方合并（最高频考点）**、Hook、resource-policy、OCI。
- **高级**抓链路与生产：完整 install 链路、崩溃恢复、三方合并失效模式、GitOps 交互、chart 架构设计、排查方法。
- **三方合并是 Helm 面试的"皇冠"**：务必能讲清"为什么三方而非两方"+ 具体例子 + list 的 merge key 行为 + 失效场景。

**参考来源**

- 前 9 章的全部内容（本章是它们的浓缩应试版）
- [Helm 官方 FAQ](https://github.com/helm/helm/blob/main/docs/faq.md)
- [helm-diff 插件](https://github.com/databus23/helm-diff)
