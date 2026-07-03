# 9. Kubernetes 最佳实践与 Trade-off

> 一句话理解：K8s 的每个配置都是 trade-off——密度 vs 容错、声明式 vs 灵活、自动化 vs 可控——本章把 AI 平台最常踩的决策点摊开，给出"什么场景选什么、为什么"。

第 8 章讲的是"生产怎么配"，本章讲"为什么这么配、什么时候反过来配"。K8s 没有银弹，一个在在线服务集群最优的配置（binpack 提密度），在训练集群可能就是灾难（单节点故障打掉整个 Job）。理解 trade-off 比记住配置更重要——配置会变，权衡逻辑不变。

> 本章每条实践都标注了**适用场景**与**反例**，避免你把"最佳"当成"普适"。

## 9.1 资源声明：requests 必填，limits 谨慎

### 规则：每个容器都设 requests

```yaml
resources:
  requests:                    # 调度依据——必填
    cpu: "4"
    memory: "16Gi"
    nvidia.com/gpu: 1
  limits:                      # 运行时上限
    nvidia.com/gpu: 1          # GPU：limit 必须等于 request（整卡独占）
    memory: "16Gi"             # 内存：limit ≈ request，防 OOM 影响节点
```

**为什么 requests 必填**：

1. **调度器靠 requests 决策**。不设 requests 的 Pod 调度时算作 0 资源，会被堆到任何节点，与有 requests 的 Pod 抢资源，导致节点超卖、驱逐风暴。
2. **QoS 等级**：`requests == limits` 的 Pod 是 `Guaranteed`（最高优先级，最后被驱逐）；只设 requests 是 `Burstable`；都不设是 `BestEffort`（最先被驱逐）。生产关键服务必须是 `Guaranteed`。
3. **HPA/VPA 依赖 requests**。不设 requests 的 Pod 无法被 HPA 基于 CPU 扩缩。

**Trade-off（CPU limits）**：是否设 CPU `limits` 是 K8s 社区长期争议。
- **设 limits**：防止单 Pod 抢光 CPU（cgroup CFS throttle），但 CFS throttle 会导致 latency 抖动（推理服务 P99 飙升）。
- **不设 limits**（推荐用于延迟敏感的推理）：CPU 可超卖借用空闲，避免 throttle，但需配合节点超卖监控。

> **AI 推理服务实践**：CPU 只设 requests 不设 limits（避免 CFS throttle 拖慢推理），内存和 GPU 设 limits（内存不超、GPU 独占）。训练任务 CPU/内存/GPU 都设 limits（保证计算稳定）。

### GPU 的特殊规则

```yaml
resources:
  limits:
    nvidia.com/gpu: 1          # 必须有 limits，且通常 limits == requests
```

GPU 资源**只能 limits 声明，不能只 requests**（Device Plugin 资源的特性）。整卡独占时 limits = 卡数；MIG/MPS 用对应扩展资源名（`nvidia.com/mig-1g.10gb`）。

## 9.2 调度策略：按负载类型选 binpack 还是 spread

| 负载 | 推荐策略 | 理由 |
|---|---|---|
| **在线推理** | binpack（`MostAllocated`） | 提密度，省机器；单 Pod 故障由 Deployment 副本兜底 |
| **训练（单 Pod）** | spread（`LeastAllocated`） | 打散到不同节点，减少单节点故障影响面 |
| **训练（多 worker）** | Gang + 拓扑感知 | all-or-nothing + 同节点 NVLink 域 |
| **批处理 Job** | binpack | 填满碎片，提升整体利用率 |
| **有状态服务**（DB） | spread + 反亲和 | 严格不同节点，避免同时挂 |

**反例**：把训练 Job 用 binpack——8 个 worker 全堆到一个 8 卡节点，该节点网络故障直接打掉整个训练，且检查点可能也在这节点上丢失。训练必须 spread + 跨节点反亲和。

```yaml
# 训练 worker 的跨节点反亲和（强制打散）
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels: { app: llm-train }
          topologyKey: kubernetes.io/hostname    # 不同 worker 不能同节点
```

## 9.3 声明式与幂等：写 YAML 的心法

K8s 的核心是**声明式 + 期望状态**。这意味着你写的 YAML 不是"执行步骤"，而是"目标快照"。由此衍生几条实践：

### 规则：控制器逻辑必须幂等

第 4、6 章反复强调：控制循环是水平触发的，可能被任意多次调用。你写的 Operator / 控制器 reconcile 必须**幂等**——无论调用几次，结果一致。

```python
# ❌ 错误：累加式逻辑（非幂等）
def reconcile(pod):
    pod.spec.replicas += 1          # 每次调用都 +1，爆炸

# ✅ 正确：基于期望状态收敛（幂等）
def reconcile(rs):
    desired = rs.spec.replicas
    actual = len(running_pods_of(rs))
    if actual < desired:
        create_pods(desired - actual)    # 只补差额
```

第 7 章模拟器的控制器就是这么写的——`_reconcile_rs` 算 `diff = replicas - len(running)`，只补差额。

### 规则：用 owner-reference 让 K8s 管级联

不要手动删除子资源。用 owner-reference（Deployment→ReplicaSet→Pod）让垃圾收集器自动级联删除。模拟器第 7 章的 `_garbage_collect_orphan_pods` 就是这个机制的简化版。

### 规则：spec 与 status 分离

CRD 设计中，**spec 是期望（用户写），status 是实际（控制器写）**。绝不要把"实际状态"写进 spec 让控制器读——这会破坏声明式语义，导致 reconcile 死循环。

```yaml
spec:          # 期望：我要 8 个 worker
  replicas: 8
status:        # 实际：当前 6 个就绪（控制器上报）
  readyReplicas: 6
```

## 9.4 健康探针：startup / readiness / liveness 各司其职

第 4 章介绍了三种探针，生产实践的关键是**不要混用**：

| 探针 | 作用 | 失败后果 | 配置要点 |
|---|---|---|---|
| **startupProbe** | 慢启动应用就绪判断 | 启动期内不触发 liveness | 大模型推理必配（加载几分钟） |
| **readinessProbe** | 是否接流量 | 失败摘流（不从 Service 删 Pod） | 灵敏，period 5-10s |
| **livenessProbe** | 是否要重启 | 失败杀 Pod 重启 | **保守**，别太敏感 |

### 大模型推理的探针配置（重点）

vLLM/Triton 这类大模型推理服务**启动慢**（加载权重几分钟到几十分钟）。错误配置会导致 Pod 被反复杀死：

```yaml
# ❌ 错误：只配 liveness，initialDelaySeconds 估不准
livenessProbe:
  httpGet: { path: /health, port: 8000 }
  initialDelaySeconds: 300        # 估 5 分钟，但大模型可能 10 分钟 → 被杀

# ✅ 正确：startupProbe 兜底慢启动，liveness 只管运行时
startupProbe:
  httpGet: { path: /health, port: 8000 }
  failureThreshold: 60            # 60 × 10s = 10 分钟启动窗口
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /health, port: 8000 }
  periodSeconds: 5
livenessProbe:
  httpGet: { path: /health, port: 8000 }
  periodSeconds: 30               # 运行后保守检查
  failureThreshold: 3             # 连续 3 次失败（90s）才重启
```

**Trade-off**：liveness 太敏感会误杀正常 Pod（网络抖动、GC 暂停），太不敏感又救不了死锁。生产经验：liveness `failureThreshold × periodSeconds` 至少 60-90s，给应用自愈机会。

## 9.5 配置管理：ConfigMap / Secret / 镜像分层

### 规则：配置与镜像分离

不要把配置打进镜像（一个模型不同环境要打不同镜像）。用 ConfigMap/Secret 注入：

```yaml
volumes:
  - name: config
    configMap: { name: vllm-config }
  - name: model-secret
    secret: { secretName: hf-token }
containers:
  - volumeMounts:
      - { name: config, mountPath: /etc/vllm }
      - { name: model-secret, mountPath: /secrets, readOnly: true }
```

### 规则：Secret 绝不入镜像、不入 Git

模型权重 token、API key、数据库密码用 Secret（或外部密钥管理 Vault / Sealed Secrets / External Secrets Operator）。Secret 在 etcd 里是 base64（不是加密！），生产要开 **encryption at rest**（etcd 静态加密）或用外部 KMS。

### 规则：镜像分层与多阶段构建

AI 镜像动辄几个 GB（CUDA + PyTorch + 模型）。生产实践：

1. **多阶段构建**：builder 阶段装编译依赖，runtime 阶段只拷产物，减小体积。
2. **基础镜像固定版本**：用 `pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime`，**不要 `latest`**（不可复现，且 Kyverno 策略会拦）。
3. **模型权重不进镜像**：用 PVC/对象存储挂载，否则每次换模型重新推几个 GB 镜像太慢。

## 9.6 有状态 vs 无状态：选对工作负载类型

| 负载 | 推荐 Workload | 理由 |
|---|---|---|
| 推理服务 | **Deployment** | 无状态，可随意滚动 |
| 训练 Job | **Job / PyTorchJob** | 跑完即止，自动清理 |
| 分布式训练 | **Job + Gang 调度** | all-or-nothing |
| 数据库/缓存 | **StatefulSet** | 稳定网络标识 + 持久卷 |
| 日志/监控 Agent | **DaemonSet** | 每节点一个 |
| 周期任务 | **CronJob** | 定时 |

**StatefulSet 的关键差异**：Pod 名稳定（`db-0`、`db-1`）、每个 Pod 独立 PVC（重启挂回自己的卷）、有序启停。适合需要稳定身份或独立存储的有状态服务。**不要用 Deployment 跑数据库**——滚动升级时 PVC 共享、Pod 名变化会出问题。

**GPU 服务的特殊性**：推理服务虽然"无状态"（权重只读），但**启动慢**，频繁滚动代价大。生产上用 `maxUnavailable: 0` + 较长 `terminationGracePeriodSeconds`，并配预热（新 Pod 就绪后才摘旧 Pod）。

## 9.7 命名与标签：可观测的基础

杂乱的命名会让运维灾难化。生产规范：

```yaml
metadata:
  name: llm-serving-vllm-7b-v3        # 应用-类型-模型-版本
  labels:
    app: llm-serving                   # 应用名
    component: vllm                    # 组件
    model: llama-7b                    # 模型
    version: v3                        # 版本（金丝雀/蓝绿用）
    tier: serving                      | 团队/层级
  namespace: team-llm                  | 团队隔离
```

**为什么重要**：selector、监控聚合、成本分摊（用 label 算每个团队花了多少 GPU）、金丝雀流量切分（按 `version` label）全依赖规范 label。提前定好命名规范，省下无数运维时间。

## 9.8 Operator：何时自研、何时用现成

AI 平台常需要自定义控制器（管理模型、训练流水线、GPU 配额）。决策：

| 场景 | 推荐 |
|---|---|
| 标准 Web/推理服务 | 用 Deployment/Service，**不要**自研 Operator |
| 多角色训练（worker/ps） | 用 Kubeflow Training Operator |
| Ray 集群 | 用 KubeRay |
| 模型仓库/版本管理 | 用 KServe / 自研轻量 Operator |
| 独特领域逻辑（如自定义训练编排） | 自研 Operator（controller-runtime + CRD） |

**自研 Operator 的红线**：不要把 Operator 当成"运行任意业务逻辑"的地方。Operator 应该是**领域知识的编码**（如何部署/扩缩/备份某类资源），不是应用本身。一个判断标准：如果逻辑可以用一个 Deployment + 脚本解决，就不要写 Operator。

自研时用 **kubebuilder / Operator SDK**（基于 controller-runtime），不要从零写 client-go——第 6 章展示了 controller-runtime 的 reconcile 模板有多简洁。

## 9.9 成本与弹性：Cluster Autoscaler / Karpenter / Spot

### 扩缩容决策

| 方案 | 适用 | 特点 |
|---|---|---|
| **HPA** | 按负载扩缩 Pod 数 | 推理服务标配（按 QPS/GPU 利用率） |
| **VPA** | 自动调 requests | 谨慎用，会重启 Pod |
| **Cluster Autoscaler** | 节点不够时加节点 | 传统方案，扩节点慢（分钟级） |
| **Karpenter** | 节点按需供给 | AWS 出品，秒级选机型，更灵活 |

**AI 负载的扩缩难点**：GPU 节点贵且扩容慢（启动新节点 + 装 GPU 驱动 + 拉镜像可能 5-10 分钟）。推理服务要**预留 buffer**（HPA 提前扩，别等满了才扩），训练任务更适合**预留池 + Gang 排队**而非即时扩容。

### Spot/抢占式实例省钱

推理服务可用 Spot 实例省钱，但必须：
1. `preemptionPolicy: Never` + 低 PriorityClass（随时被驱逐）。
2. 多副本跨可用区（一个 AZ 的 Spot 被回收不影响全部）。
3. 优雅关停（`SIGTERM` 处理 + 快速重启）。

**训练任务慎用 Spot**——被驱逐代价大（检查点丢失）。要么用弹性训练（PyTorch Elastic + 频繁 checkpoint），要么别用 Spot 跑长训练。

## 9.10 反模式清单（务必避免）

最后，把最常见的"坑"集中列出。这些是生产事故的高频来源：

| 反模式 | 后果 | 正确做法 |
|---|---|---|
| **不设 resources.requests** | 调度混乱、QoS 降级、节点超卖 | 所有容器设 requests |
| **用 `latest` 镜像 tag** | 不可复现、滚动行为不可控 | 固定版本或 digest |
| **Deployment 跑数据库** | 滚动时数据丢失/PVC 冲突 | 用 StatefulSet |
| **训练不用 Gang 调度** | worker 部分启动死锁 | Volcano/scheduler-plugins |
| **GPU Pod 不设 priorityClass** | 被低优先级任务抢占、调度无序 | 建优先级体系 |
| **livenessProbe 过于敏感** | 误杀正常 Pod（GC/网络抖动） | 保守配 + startupProbe 兜底 |
| **大模型推理不配 startupProbe** | 启动慢被 liveness 杀死，循环重启 | startupProbe + 大 failureThreshold |
| **Secret 明文进镜像/Git** | 凭证泄露 | Secret + 静态加密 + KMS |
| **不备份 etcd** | 集群灾难无法恢复 | 定时快照 + 外部存储 + 恢复演练 |
| **operator 当业务逻辑跑** | 复杂难维护、绑定 K8s | 区分领域编排与应用逻辑 |
| **所有 Pod 同 namespace/无 NetworkPolicy** | 多租户互相干扰、安全风险 | 按团队 ns + NetworkPolicy + ResourceQuota |
| **跨 K8s 版本不查弃用 API** | 升级后资源消失 | `kubent`/`pluto` 预扫描 |

## 本章小结

K8s 最佳实践的本质是**在矛盾的目标间做权衡**：密度 vs 容错（binpack vs spread）、声明式的简洁 vs 灵活性（spec/status 分离、幂等 reconcile）、自动化 vs 可控（探针灵敏度、扩缩 buffer）、成本 vs 稳定（Spot vs 按量、预留 vs 即时）。AI 平台的核心实践可浓缩为：requests 必填且按负载选 QoS；调度策略与负载匹配（推理 binpack、训练 spread+Gang+拓扑）；探针三件套各司其职且大模型必配 startupProbe；配置与镜像分离、Secret 不入库；选对 Workload 类型（StatefulSet 只给有状态）；标签命名规范化支撑可观测与成本分摊；Operator 只编码领域知识不当业务跑；扩缩给 buffer、Spot 谨慎用于训练。最后那张反模式清单是事故的高频来源——每一条都对应真实生产事故，务必在团队规范里固化为不可绕过的护栏（Kyverno 策略是固化它们的好工具）。

**参考来源**

- [Kubernetes 资源管理（requests/limits/QoS）](https://kubernetes.io/zh-cn/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes 工作负载最佳实践](https://kubernetes.io/zh-cn/docs/concepts/workloads/)
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Karpenter](https://karpenter.sh/)
- [kubebuilder / Operator SDK](https://book.kubebuilder.io/)
- [Kubernetes Anti-Patterns（社区合集）](https://learnk8s.io/)
