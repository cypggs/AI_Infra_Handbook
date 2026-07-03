# 1. 背景：从"人肉运维"到自管理应用

> 一句话理解：Operator 模式诞生于一个朴素痛点——**有状态/复杂应用（数据库、消息队列、ML 训练作业）靠人写 runbook + 手敲 kubectl 根本管不过来**；CoreOS 在 2016 年提出"把领域专家的运维知识编码成一个跑在集群里的控制循环"，让 Kubernetes 像管理 Pod 一样自动管理这些应用。这一章回答：Operator 到底解决什么、它和 Helm/脚本/CI 有什么不同、为什么 AI 平台离不开它。

## 1.1 痛点：复杂应用靠人管不动

先看 Kubernetes **内置 Controller** 管什么。K8s 自带 `Deployment`/`ReplicaSet`/`StatefulSet`/`DaemonSet`/`Job`/`CronJob` 等一组通用工作负载 Controller，它们的核心能力是：

> **"声明 N 个 Pod 副本，控制循环持续保证集群里正好有 N 个健康副本在跑。"**

这对**无状态应用**（web 服务、API 网关）足够了——Pod 是同质的，挂了重启即可。但对下面这类应用，内置 Controller **力不从心**：

| 应用 | 人需要做的运维（runbook） |
|---|---|
| **PostgreSQL/MySQL** | 主从拓扑、故障转移（promote 从库）、备份/恢复（PITR）、版本升级（先升 replica 再升 primary）、连接池调参 |
| **Kafka/Redis Cluster** | 分区重平衡、broker 上下线、副本迁移、机架感知 |
| **etcd** | 成员变更、快照、压缩、法定人数维护 |
| **分布式训练作业（PyTorch/TF/MPI）** | 启动 chief/worker/ps、leader 选举、检查点、失败 worker 续训、作业完成清理 |
| **Ray 集群** | head/worker 拓扑、autoscaling、节点故障重建、对象存储 spill |
| **推理服务（vLLM/Triton）** | 多副本 + 模型加载、金丝雀、扩缩到零、版本切换不丢请求 |

这些运维动作有几个共同特征，让它们**无法被 `Deployment` 表达**：

1. **领域知识**：什么时候该 promote 从库？备份该怎么做？训练作业的 chief 挂了 worker 怎么处理？——这些是**专家知识**，不是"复制 N 个 Pod"能概括的。
2. **多资源协同**：一个 Ray 集群 = head Service + head Deployment + worker StatefulSet + 若干 ConfigMap/Role；一个训练作业 = 多个角色 Pod + PVC + Service。它们必须**一起**创建、一起升级、一起清理。
3. **生命周期长且有状态**：数据库有数据，训练作业有 checkpoint，删了重建会丢东西。需要**有序**操作（先备份再升级、先 drain 再删）。
4. **外部世界交互**：备份要推 S3、故障转移要改 DNS、完成要发通知。

### 传统做法及其失败模式

在没有 Operator 的时代，团队用三种方式管这些应用，每种都有致命缺陷：

**做法 A：纯手动 kubectl + runbook 文档**

```
故障转移 runbook（摘自某公司 wiki，60 步）：
1. kubectl exec 进 primary 确认不可用
2. 选一个 replica，确认它 replay 到最新 WAL
3. kubectl patch postgres-cluster ... promote
4. 改 Service 指向新 primary
5. ...（凌晨 3 点，你在电话里念这 60 步）
```

失败模式：人会犯错（尤其凌晨）、文档会过期、不同人操作不一致、没法自动化扩容。**每次故障都是一次惊魂**。

**做法 B：Bash/Python 脚本 + CI**

把 runbook 写成脚本，CI 定时跑或事件触发。

失败模式：脚本是 **edge-triggered**（"收到告警 → 跑一次"），漏掉中间状态变化就不再纠正；脚本不在集群里、没有 K8s 的 watch 能力、退出后状态丢失；多副本协调靠外部锁；和 K8s 声明式模型**两套真相源**打架。本质是"在 K8s 之外重建一个简陋的 K8s"。

**做法 C：Helm + 大量 Hooks**

用 Helm 部署，靠 `pre-install`/`post-upgrade` Hook 跑运维逻辑。

失败模式：Helm 的核心是**一次性渲染安装**（见 [Helm 第 1 章](../helm/01-background)），Hook 只在 install/upgrade 时跑，**不持续监控**。Pod 挂了 Helm 不知道，更不会做故障转移。把持续运维逻辑塞进 Hook 是用错了工具。

## 1.2 Operator 的提出：把专家知识变成控制循环

2016 年 11 月，CoreOS（后被 Red Hat 收购）发表 [《Introducing Operators》](https://coreos.com/blog/introducing-operators.html)，正式定义了 Operator 模式：

> **An Operator is a method of packaging, deploying and managing a Kubernetes application. ... It builds upon the primary Kubernetes resource and controller concepts but includes domain or application-specific knowledge.**
>
> （Operator 是打包、部署、管理一个 K8s 应用的方法。它在 K8s 的"资源 + 控制器"基础概念之上，**嵌入了领域/应用特定的知识**。）

这个定义的核心洞察是：

> **Kubernetes 内置 Controller（如 Deployment Controller）和用户写的 Operator，在机制上完全同构——都是"watch 资源 → 调和到期望状态"的控制循环。区别只是：内置 Controller 管的是通用抽象（Pod 副本数），Operator 管的是领域对象（一个数据库集群、一个训练作业）。**

换句话说，**Operator 不是新机制，而是 K8s 控制平面的"用户态扩展"**。K8s 给了你两个扩展点，Operator 把它们组合起来：

1. **CRD（CustomResourceDefinition）**——让用户定义自己的资源类型（如 `RayCluster`、`PyTorchJob`），它和 Pod/Service 一样进 etcd、一样能 `kubectl get`、一样受 RBAC 保护。这让 K8s 的 API 从"固定的一组内置资源"变成**可编程的领域 API**。
2. **自定义 Controller**——一段跑在集群里（通常是个 Deployment）的代码，watch 你的 CR（和它关心的子资源），运行领域特定的 reconcile 逻辑。

二者结合，Operator 把"运维专家"编码成"永远在线、自动纠偏的代码"：

```
   用户：kubectl apply -f raycluster.yaml (期望：1 head + 4 worker)
            │
            ▼
   ┌─────────────────────────────────────────┐
   │  RayCluster Controller（永远在线）        │
   │  watch RayCluster CR →                   │
   │  发现集群里只有 1 head + 2 worker →       │
   │  创建 2 个 worker Pod →                   │
   │  watch 到新 Pod ready → 更新 CR status    │
   │  (持续循环，任何偏离都会被纠正)            │
   └─────────────────────────────────────────┘
            │
            ▼
   集群现状 ≡ 期望状态（最终一致）
```

这个模型继承了 K8s 内置 Controller 的全部优点（声明式、level-triggered、幂等、自愈），只是把"调和逻辑"从"保证 N 个 Pod"换成"保证一个健康的数据库集群 / 一个跑起来的训练作业"。

### 一个关键类比：Operator = K8s 的"应用层 Controller"

如果你读过 [Kubernetes 第 4 章](../kubernetes/04-runtime-workflow)，你已经见过 Deployment Controller 的控制循环。Operator 和它**结构完全一样**：

| 维度 | Deployment Controller（内置） | RayCluster Operator（用户写） |
|---|---|---|
| 管理的资源 | Deployment / ReplicaSet / Pod | RayCluster CR / head+worker Pod / Service |
| watch 什么 | Deployment 变化、Pod 变化 | RayCluster CR 变化、子 Pod/Service 变化 |
| reconcile 做什么 | 保证 Pod 副本数 = spec.replicas | 保证 Ray 集群拓扑/状态 = spec 描述 |
| 触发模型 | level-triggered（基于当前全量状态） | level-triggered |
| 幂等性 | 多次 reconcile 结果一致 | 多次 reconcile 结果一致 |
| 跑在哪 | kube-controller-manager（控制平面） | 集群里一个普通 Deployment（用户态） |

> **结论**：理解了 K8s 内置 Controller，你就理解了 Operator 的 90%。剩下的 10% 是 CRD 和领域逻辑。这也是为什么本主题高度依赖 [Kubernetes 篇](../kubernetes/)——建议先读 K8s 第 3（架构）、4（Runtime 工作流程）章。

## 1.3 Operator 解决了什么（和不解决什么）

**Operator 解决**：

- ✅ **持续调和**：CR 一旦声明期望状态，Controller 持续保证现状趋近它——Pod 挂了自动重建、节点故障自动迁移、spec 改了自动应用。
- ✅ **领域自动化**：故障转移、备份、扩缩容、版本升级等专家动作，编码进 reconcile，不再靠人/runbook。
- ✅ **多资源协同 + 级联生命周期**：一个 CR 对应一组子资源，Owner Reference 保证 CR 删了子资源自动清理（垃圾回收）。
- ✅ **声明式领域 API**：用户只需 `kubectl apply` 一个 `RayCluster`，不用关心底层 Pod/Service 细节——API 上升到了"业务语义"层。
- ✅ **可观测**：CR 的 `status` 字段 + events + Controller metrics 暴露应用真实状态。

**Operator 不解决**：

- ❌ **一次性安装的复杂参数化**：那是 Helm 的活（见 [Helm 第 1 章](../helm/01-background)）。Operator 本身常用 Helm 部署。
- ❌ **批处理作业编排（DAG、人工审批、分支）**：那是 Argo Workflow / Tekton 的活。Operator 适合"长期运行 + 自愈"的 workload，不是"一次性流水线"。
- ❌ **服务网格/流量治理**：那是 Istio/Linkerd 的活。
- ❌ **替代所有运维**：Operator 是代码，代码有 bug；它降低而非消除运维负担，仍需监控、升级、修 Operator 自己的故障。

## 1.4 Operator vs Helm vs 脚本 vs Argo Workflow

一个常见困惑：这么多工具，我的需求该用哪个？下面这张表是 AI 平台选型的核心参考：

| 工具 | 核心模型 | 触发 | 持续性 | 典型场景 |
|---|---|---|---|---|
| **Helm** | 模板渲染 + 参数 + 一次性 apply | 手动/CI 触发 | 一次性（装完即走） | 装应用、装 Operator 本身、参数化部署 |
| **Operator** | CRD + 控制循环（持续 reconcile） | 声明 CR，自动持续 | 永远在线、自愈 | 管理有状态/复杂应用（数据库、训练作业、推理服务、Ray） |
| **脚本/CI** | 命令式脚本 | 事件/定时 | 一次性、edge-triggered | 一次性迁移、数据初始化 |
| **Argo Workflow** | DAG 步骤 + 模板 | 手动/事件 | 一次性（流水线） | 训练流水线、数据处理、CI/CD |
| **K8s Job/CronJob** | 跑完即退出的 Pod | 手动/定时 | 一次性/周期 | 批处理任务、定时备份触发器 |

**判定法则**：

- **要"装一次 + 偶尔升级"，参数多** → **Helm**。
- **要"长期运行 + 自动纠偏 + 多资源协同 + 领域逻辑"** → **Operator**。
- **要"有头有尾的一次性流水线（DAG）"** → **Argo Workflow**。
- **要"定时/一次性跑个任务"** → **Job/CronJob**。

> **最常见的组合**：**Helm 装 Operator，Operator 管业务实例**。比如用 Helm 部署 KubeRay Operator（一次），之后创建 `RayCluster` CR（Operator 持续管）。Helm 和 Operator 不是竞争，是分层。

## 1.5 AI 平台为什么需要 Operator

AI 工作负载几乎完美命中"需要 Operator"的全部特征：

| 特征 | AI 场景体现 | 典型 Operator |
|---|---|---|
| **领域知识密集** | 分布式训练的 chief/worker 角色、allreduce/PS 通信、checkpoint 续训 | Training Operator（PyTorchJob/TFJob/MPIJob） |
| **多资源协同** | Ray 集群 = head + workers + Service + autoscaler 配置 | KubeRay（RayCluster/RayService） |
| **弹性 + 自愈** | 推理服务按 QPS 自动扩缩、节点故障自动迁移、闲时缩到零 | KServe（InferenceService）、vLLM Operator |
| **生命周期复杂** | 模型加载（几分钟）、版本金丝雀、权重 PVC 保留 | 推理类 Operator |
| **硬件特化** | GPU 驱动、MIG 切分、Device Plugin、DCGM 监控 | NVIDIA GPU Operator |

更重要的是，AI 平台**本身就是一个"自管理平台"**：它的目标就是让算法工程师 `kubectl apply` 一个训练/推理意图，平台自动完成资源调度、环境准备、监控、故障恢复。这个"意图 → 自动执行"的核心抽象，**正是 Operator 提供的**。可以说：

> **没有 Operator，就没有现代云原生 AI 平台。** Kubeflow、Ray on K8s、KServe、各家的推理平台，底层都是一组 Operator。

## 本章小结

- **痛点**：有状态/复杂应用（数据库、消息队列、训练作业、推理服务）的运维靠 runbook + 手动 kubectl 管不动——领域知识密集、多资源协同、生命周期复杂、需与外部世界交互。
- **传统方案的失败**：手动（人会错、文档过期）、脚本/CI（edge-triggered、无 watch、两套真相源）、Helm Hooks（一次性、不持续监控）都解决不了"持续自愈"。
- **Operator 的定义**（CoreOS 2016）：把领域专家的运维知识编码成"跑在集群里的控制循环"，通过 CRD 扩展 K8s API，让 K8s 自动管理任意复杂应用。
- **核心洞察**：Operator 与 K8s 内置 Controller **机制同构**（都是 level-triggered、幂等的控制循环），只是管的是领域对象而非通用 Pod 副本数。理解 K8s Controller 就理解了 Operator 的 90%。
- **定位**：Operator 和 Helm 互补——Helm 装 Operator，Operator 管业务；AI 平台的自管理特性几乎全靠 Operator 实现（KubeRay、Training Operator、KServe、vLLM Operator、GPU Operator）。

**参考来源**

- [CoreOS — Introducing Operators (2016)](https://coreos.com/blog/introducing-operators.html) —— Operator 模式的原始定义。
- [Kubernetes Patterns — The Operator Pattern (Red Hat)](https://www.redhat.com/en/resources/oreilly-kubernetes-patterns-cloud-native-apps) —— Kubernetes Patterns 书把 Operator 列为核心模式之一。
- [Kubernetes 官方 — Operator pattern](https://kubernetes.io/zh-cn/docs/concepts/extend-kubernetes/operator/) —— 官方对 Operator 模式的描述。
- 本手册 [Kubernetes 第 4 章](../kubernetes/04-runtime-workflow)（控制循环）、[Helm 第 1 章](../helm/01-background)（一次性安装 vs 持续管理）。
