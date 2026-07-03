# 8. Kubernetes 生产实践：把 AI 平台安全地跑在 K8s 上

> 一句话理解：在 K8s 上跑 AI 平台，难点不在"能不能跑起来"，而在**GPU 利用率、训练任务的全或无调度、多租户隔离、滚动升级零中断、故障自愈**这些生产级问题——本章给出经过验证的落地配置与排错路径。

第 7 章的模拟器让你理解了机制，但生产环境的复杂度远不止于此：真实集群有几千个 Pod、上百张 GPU、十几个团队共享，还有网络、存储、安全、成本的真实约束。本章把这些**生产才有的问题**集中讲透，按"集群底座 → AI 工作负载 → 调度优化 → 可观测性 → 安全 → 故障排查"六个维度给出可操作的实践。

> 本章假设你已读第 3、4、5 章（架构 / 运行流程 / 核心模块）。所有配置示例都标注了适用版本，K8s 当前以 v1.30 LTS / v1.36（含原生 PodGroup）为参考。

## 8.1 集群底座：控制平面高可用与节点池规划

### 控制平面高可用（HA）

生产集群控制平面必须多副本。核心原则：

| 组件 | HA 方式 | 说明 |
|---|---|---|
| **kube-apiserver** | 无状态，水平扩 | 前面挂 LB（每个 apiserver 前置健康检查），可任意多副本 |
| **etcd** | Raft 法定数 | **3 或 5 个节点**（奇数）；3 节点容忍 1 故障，5 节点容忍 2 故障。AI 平台用 5 节点更稳 |
| **kube-scheduler / controller-manager** | 选主（leader election） | 多副本但只有 1 个 active，靠 `--leader-elect` |

```yaml
# etcd 生产关键参数（5 节点集群）
--initial-cluster etcd0=https://etcd0:2380,...,etcd4=https://etcd4:2380
--heartbeat-interval=250          # 心跳间隔（ms），跨机房可调大
--election-timeout=2500           # 选举超时，建议 ≥ 心跳 × 10
--quota-backend-bytes=8589934592  # 8GiB 配额，AI 平台 CRD 多易超 2GiB 默认值
--auto-compaction-retention=5     # 自动压缩保留 5 小时历史，防 DB 膨胀
```

**踩坑**：etcd 是整个集群的命脉。常见故障是磁盘 IO 抖动导致心跳超时、leader 频繁切换。生产上 etcd 必须用**独占 SSD/NVMe**，绝不要和业务负载混部。监控 `etcd_disk_wal_fsync_duration_seconds` 的 P99，超过 10ms 就要告警。

### GPU 节点池：专用 + 污点

AI 平台几乎都把 GPU 节点做成**专用节点池**，用污点（Taint）阻止非 GPU 任务占用：

```yaml
# 给所有 GPU 节点打污点：只有声明了 GPU + 容忍度的 Pod 才能上来
kubectl taint nodes gpu-pool nvidia.com/gpu=present:NoSchedule
kubectl label nodes gpu-pool node.kubernetes.io/instance-type=gpu --all

# GPU Pod 必须同时声明资源 + 容忍度
spec:
  containers:
    - name: trainer
      resources:
        limits:
          nvidia.com/gpu: 8           # 整节点 8 卡（独占）
      # ...
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists                # 容忍 GPU 污点
  nodeSelector:
    node.kubernetes.io/instance-type: gpu
  priorityClassName: training-high    # 训练高优先级
```

**为什么 NoSchedule 而不是 NoExecute**：`NoSchedule` 只阻止新调度，已在运行的 Pod 不受影响；`NoExecute` 会驱逐已运行的 Pod。GPU 训练任务跑起来很贵（检查点、初始化），用 `NoExecute` 可能误杀长任务。生产上多用 `NoSchedule`。

## 8.2 GPU 工作负载：Device Plugin、MIG、共享与拓扑

### NVIDIA GPU Operator：一键部署 GPU 栈

裸装 GPU 驱动、containerd 的 NVIDIA runtime、Device Plugin 是个容易出错的苦差事。生产上几乎都用 **NVIDIA GPU Operator**（一个 Operator 自动管理这一整套）：

```yaml
# Helm 安装 GPU Operator（生产推荐方式）
helm install --wait gpu-operator \
  nvidia/gpu-operator \
  -n gpu-operator --create-namespace \
  --set driver.enabled=true \
  --set toolkit.enabled=true \
  --set devicePlugin.enabled=true \
  --set dcgmExporter.enabled=true       # 同时装 DCGM 监控导出器
```

Operator 会给每个 GPU 节点部署：驱动（或用宿主机驱动）、`nvidia-container-toolkit`（让 CRI 能用 GPU）、Device Plugin（上报 `nvidia.com/gpu`）、DCGM-Exporter（Prometheus 指标）、MIG Manager（可选）。

### MIG：把一张 H100 切成 7 份

A100/H100 支持 **MIG（Multi-Instance GPU）**，把一张卡硬件切分成多个隔离实例，适合并发跑多个小推理服务（提高利用率）：

```yaml
# GPU Operator 开启 MIG（以 1g.10gb 为例：1 个 GI，10GB 显存）
apiVersion: nvidia.com/v1
kind: Policy
spec:
  migStrategy: mixed                 # 单节点上混合多种 MIG 切法
  resources:
    - name: nvidia.com/mig-1g.10gb
      devices: 4                     # 切出 4 个 1g.10gb 实例
# Pod 用扩展资源声明
resources:
  limits:
    nvidia.com/mig-1g.10gb: 1
```

**何时用 MIG vs MPS vs 整卡**：

| 方式 | 隔离性 | 利用率 | 适用场景 |
|---|---|---|---|
| **整卡独占** | 最高（硬件级） | 低（小模型浪费） | 训练、大模型推理 |
| **MIG** | 高（硬件级隔离） | 中高 | 多个中小模型并发推理 |
| **MPS** | 低（进程级，共享 SM） | 高 | 同团队多个任务、可信租户 |
| **vGPU（时间片）** | 低 | 中 | 旧卡（非 Ampere+） |

AI 平台对推理服务常配 MIG，对训练保持整卡独占。

### GPU 拓扑感知调度（NVLink/NVSwitch）

8 卡节点内部 GPU 之间有 NVLink/NVSwitch，跨卡通信带宽天差地别。分布式训练对拓扑敏感——把一个训练 Job 的 worker 调到**同一个节点的 8 张卡**远好于跨节点（跨节点走 InfiniBand/RoCE，延迟高一个量级）。生产上用 **scheduler-plugins 的 `NodeResourceTopology`** 插件，或 v1.36 之后的拓扑感知调度能力：

```yaml
# NodeResourceTopology 插件感知 NUMA / GPU 拓扑
# 调度器优先把一个 Pod 的所有 GPU 请求放到同一 NVSwitch 域
```

模拟器第 7 章没实现拓扑（简化），但生产训练必须考虑——这是为什么大模型训练平台（如 Ray Train、Megatron on K8s）都要自定义调度器或拓扑亲和规则。

## 8.3 分布式训练：Gang 调度与 Operator

### 为什么必须 Gang 调度

第 1、7 章已论述：分布式训练要求所有 worker 同时启动。在 K8s 上不加 Gang 调度会出现**死锁**——8 个 worker 的 Job，如果只调度成功 5 个，这 5 个会卡在 `init_process_group` 等剩下 3 个，而剩下 3 个可能因为别的任务占着资源永远调不上来。结果是整个集群的训练任务互相阻塞。

生产上三种方案，按推荐度排序：

| 方案 | 调度器 | 成熟度 | 适用 |
|---|---|---|---|
| **Volcano** | 独立调度器（替代 kube-scheduler） | 生产成熟，国内广泛 | 训练为主的大规模平台 |
| **scheduler-plugins Coscheduling** | 第二调度器（与默认并存） | 稳定，CNCF | 想保留默认调度器的混合负载 |
| **v1.36 原生 PodGroup** | kube-scheduler 内置 | GA 早期（2025+） | 新集群、想用原生方案 |

```yaml
# Volcano 的 PodGroup + Job（生产训练标准写法）
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: llm-train-pg
spec:
  minMember: 8                     # 必须 8 个全调度成功才放行
  priorityClassName: training-high
  queue: default                   # 可配队列做公平调度
---
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: llm-train
spec:
  minAvailable: 8                  # all-or-nothing
  schedulerName: volcano
  policies:
    - event: PodEvicted
      action: RestartJob           # worker 被驱逐 → 整 Job 重启（保留检查点）
  tasks:
    - replicas: 8
      template:
        spec:
          containers:
            - name: trainer
              resources:
                limits: { nvidia.com/gpu: 8 }
```

**关键配置 `minAvailable`**：等于 worker 数即严格 all-or-nothing；小于则允许部分启动（弹性训练，如弹性 PyTorch）。生产大模型训练通常设为全量，弹性训练（Elastic）才设小于。

### Kubeflow Training Operator / Ray Train

直接写 PodGroup 较底层。生产多用上层 Operator：

- **Kubeflow Training Operator**（原 `tf-operator`/`pytorch-operator`）：CRD `PyTorchJob`/`MPIJob`，封装 worker/ps 角色模板 + Gang 调度集成。
- **Ray Train / KubeRay**：`RayCluster` CRD + 自动扩缩，Ray 自带 actor 级调度，与 K8s 调度协作（见本手册 Ray 主题）。

```yaml
# PyTorchJob 示例（Kubeflow Training Operator）
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata: { name: llm-ddp }
spec:
  pytorchReplicaSpecs:
    Worker:
      replicas: 8
      template:
        spec:
          schedulerName: volcano          # 用 Gang 调度器
          containers:
            - name: pytorch
              resources:
                limits: { nvidia.com/gpu: 8 }
```

## 8.4 调度优化：从默认到 AI 友好

默认 kube-scheduler 的 `NodeResourcesFit(MostAllocated)` + `SelectorSpread` 对 AI 负载**不友好**——binpack 会把 GPU Pod 堆到少数节点（一旦这些节点挂了影响大），spread 又可能把训练 worker 拆散到拓扑差的节点。生产 AI 集群的调度器配置要点：

### 关闭默认 binpack，改用拓扑感知 + 公平

```yaml
# kube-scheduler-policy（或 KubeSchedulerConfiguration）
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
  - schedulerName: default-scheduler
    pluginConfig:
      - name: NodeResourcesFit
        args:
          scoringStrategy:
            type: LeastAllocated        # 反 binpack：AI 负载偏好打散
      - name: NodeResourceTopology      # 拓扑感知（scheduler-plugins）
      - name: Coscheduling              # Gang（scheduler-plugins，第二调度器）
```

### PriorityClass 与抢占

AI 平台必须有清晰的优先级体系，否则训练任务和在线推理互相抢占会一团糟：

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: { name: production-serving }
value: 1000000
globalDefault: false
description: "生产推理服务，最高优先，可抢占训练"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: { name: training-high }
value: 500000
description: "正式训练任务"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: { name: spot-experimental }
value: 100000
preemptionPolicy: Never                # 不抢占别人，自己随时被抢（Spot 风格）
description: "实验/抢占式，随时可被驱逐"
```

**抢占的代价**：抢占会驱逐低优先级 Pod，对训练任务意味着检查点丢失（除非配 `RestartJob` + 检查点恢复）。生产上对长训练任务要配 **PDB（PodDisruptionBudget）** 和定期 checkpoint，把抢占损失降到分钟级。

### Descheduler：周期重平衡

集群跑久了会出现负载不均（新 Pod 用 spread，但节点陆续下线后倾斜）。生产上常跑 **Descheduler**（独立组件，定期驱逐可迁移 Pod 让调度器重新平衡）：

```yaml
# Descheduler 策略：低利用率节点上的 Pod 迁走
apiVersion: "descheduler/v1"
kind: "DeschedulerPolicy"
strategies:
  LowNodeUtilization:
    enabled: true
    params:
      nodeResourceUtilizationThresholds:
        thresholds: { cpu: 20, memory: 20, gpu: 20 }   # 低于 20% 利用率的节点
        targetThresholds: { cpu: 50, memory: 50, gpu: 50 }
```

> 注意：Descheduler 对**有状态/训练任务要慎用**——驱逐正在训练的 Pod 代价大。生产上给训练 Pod 打 `descheduler.alpha.kubernetes.io/evict: "false"` 注解豁免。

## 8.5 可观测性：监控、指标与告警

K8s 可观测性是三个支柱：**Metrics（指标）、Logs（日志）、Traces（链路）**。AI 平台还要加 GPU 指标。

### 必装监控组件

| 组件 | 作用 | 关键指标 |
|---|---|---|
| **Metrics Server** | 给 HPA/VPA 提供实时 CPU/内存 | `metrics.k8s.io` API |
| **kube-state-metrics** | 暴露集群对象状态（Pod/Deployment/Node） | `kube_pod_status_phase`、`kube_deployment_status_replicas_available` |
| **Prometheus** | 指标采集存储 + PromQL | scrape 所有 exporter |
| **DCGM-Exporter** | NVIDIA GPU 指标 | `DCGM_FI_DEV_GPU_UTIL`、`DCGM_FI_DEV_FB_USED`（显存） |
| **node-exporter** | 节点级 CPU/内存/磁盘/网络 | `node_cpu_seconds_total` |
| **Loki / ELK** | 日志聚合 | Pod 日志集中查询 |

### AI 平台特有关键指标与告警

```promql
# 1. GPU 利用率低告警（推理服务空跑浪费卡）
avg by (pod) (DCGM_FI_DEV_GPU_UTIL) < 10
# → 持续 30min 利用率 < 10%，可能是 batch 不足或死循环

# 2. GPU 显存即将 OOM
DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL > 0.95
# → 显存 > 95%，随时 OOM，需扩容或排查泄漏

# 3. Pod 持续 Pending（调度失败）
kube_pod_status_phase{phase="Pending"} == 1  # 持续 10min
# → 看 kubectl describe 的 Events：是资源不足、亲和性、还是污点

# 4. Deployment 副本数不达标
kube_deployment_status_replicas_available < kube_deployment_spec_replicas
# → 滚动升级卡住或 Pod 持续崩溃

# 5. 节点 NotReady
kube_node_status_condition{condition="Ready",status!="true"} == 1
# → 节点失联，kubelet 异常或网络分区

# 6. 训练 Job 重建频繁（被抢占或崩溃）
rate(kube_pod_container_status_restarts_total[15m]) > 0
```

### GPU 利用率是 AI 平台的核心 KPI

整个 AI 平台的"单位推理成本"取决于 GPU 利用率。生产上把 `avg(DCGM_FI_DEV_GPU_UTIL)` 做成团队级看板，目标通常 > 60%（推理）/ > 90%（训练）。利用率低就启动 vLLM 连续批处理、Triton dynamic batching、或 MIG 切分（见本手册 vLLM/Triton 主题）。

## 8.6 安全：RBAC、网络策略与多租户

### RBAC：最小权限

AI 平台多团队共享，必须用 RBAC 限制每个团队只能操作自己的 namespace：

```yaml
# 给某团队绑一个 namespace 内的编辑权限（不能动别的 ns）
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: { namespace: team-llm, name: team-llm-editor }
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "configmaps", "pods/log"]
    verbs: ["get", "list", "create", "update", "delete"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["*"]
---
kind: RoleBinding
metadata: { namespace: team-llm, name: team-llm-bind }
subjects: [{ kind: Group, name: "team-llm@corp.com", apiGroup: "rbac.authorization.k8s.io" }]
roleRef: { kind: Role, name: team-llm-editor, apiGroup: "rbac.authorization.k8s.io" }
```

**最佳实践**：宁可给少，逐步加。绝不要给团队 `cluster-admin` 或跨 namespace 权限。用 `kubectl auth can-i --list` 验证实际权限。

### Admission：强制策略（Kyverno / OPA Gatekeeper）

光靠 RBAC 不够，还要用**准入策略**防止误操作。生产 AI 平台常用 **Kyverno**（声明式策略，比 OPA Gatekeeper 易用）强制：

```yaml
# Kyverno 策略：所有 GPU Pod 必须设 resources.limits 和 priorityClass
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: { name: require-gpu-limits }
spec:
  rules:
    - name: require-gpu-limits
      match: { resources: { kinds: ["Pod"] } }
      validate:
        message: "申请 nvidia.com/gpu 的 Pod 必须设 limits 和 priorityClassName"
        pattern:
          spec:
            containers:
              - resources: { limits: { nvidia.com/gpu: "?*" } }
            priorityClassName: "?*"
```

类似策略还有：禁止 `latest` 镜像 tag、强制配 ResourceQuota、禁止特权容器、强制镜像来自可信仓库。这些策略把"最佳实践"变成**不可绕过的护栏**。

### 网络策略（NetworkPolicy）

默认 K8s Pod 之间网络全通。多租户必须用 NetworkPolicy 隔离：

```yaml
# team-llm namespace 的 Pod 只能互相通，拒绝其他 namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { namespace: team-llm, name: deny-cross-ns }
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector: {}              # 仅同 namespace 内 Pod
```

> 注意 NetworkPolicy 需 CNI 支持（Calico/Cilium 支持，Flannel 默认不支持）。AI 平台多租户强烈建议用 Calico 或 Cilium。

### 资源配额（ResourceQuota + LimitRange）

防止单个团队/Job 耗尽集群资源：

```yaml
apiVersion: v1
kind: ResourceQuota
metadata: { namespace: team-llm, name: compute-quota }
spec:
  hard:
    requests.nvidia.com/gpu: "32"      # 该团队最多占 32 张 GPU
    requests.cpu: "200"
    requests.memory: 1000Gi
    pods: "200"
```

## 8.7 故障排查手册：从症状到根因

生产故障排查的核心是**顺着一个 Pod 的生命周期倒推**（第 4 章）。下面是高频故障的症状 → 定位 → 根因表：

### Pod 一直 Pending

```bash
kubectl describe pod <pod> | grep -A20 Events
```

| 事件信息 | 根因 | 解决 |
|---|---|---|
| `0/8 nodes are available: insufficient nvidia.com/gpu` | GPU 不够 | 扩节点 / 提交 Gang 调度排队 / 减小 worker 数 |
| `node(s) had untolerated taint` | 没容忍 GPU 污点 | 加 toleration |
| `node(s) didn't match Pod's node affinity` | nodeSelector/亲和性不匹配 | 检查 label |
| `Insufficient memory` | 内存不够 | 减 requests 或扩节点 |

### Pod 卡在 ContainerCreating

通常是运行时/网络/存储问题：

```bash
kubectl describe pod <pod> | grep -A20 Events
```

| 症状 | 根因 | 解决 |
|---|---|---|
| `failed to setup network` | CNI 未装/故障 | 装 Calico/Cilium；检查节点上 CNI pod |
| `ImagePullBackOff` | 镜像拉不下来 | 检查仓库凭证、网络、镜像名 |
| `MountVolume.SetUp failed` | CSI/PV 问题 | 检查 StorageClass、PV/PVC 绑定 |
| `CreateContainerConfigError`（GPU 相关） | Device Plugin/NVIDIA runtime 异常 | 检查 GPU Operator、`nvidia-smi` |

### Pod 反复 CrashLoopBackOff

```bash
kubectl logs <pod> --previous        # 看上一次崩溃的日志
```

最常见根因：应用启动失败（配置错、依赖连不上、OOM）。**注意区分 OOMKilled 和应用 panic**：

```bash
kubectl describe pod <pod> | grep -i "Last State"
# OOMKilled: 退出码 137 → 调大 memory limit
# Exit 1/139: 应用异常 → 看日志
```

### GPU 相关

```bash
# 节点上看 GPU 状态
nvidia-smi
# Pod 里看是否真的拿到 GPU
kubectl exec <pod> -- nvidia-smi
# 若容器内看不到 GPU → NVIDIA runtime 没配好（GPU Operator）
```

### 集群级故障

- **大面积 Pod Pending**：很可能调度器/controller-manager 挂了或 etcd 不可用 → 查控制平面 pod 状态。
- **apiserver 响应慢**：`kubectl get` 卡顿 → etcd 磁盘 IO 抖动或 apiserver 过载（看 apiserver metrics `apiserver_request_duration_seconds`）。
- **节点 NotReady**：kubelet 与 apiserver 失联 → SSH 上节点看 `kubelet` 日志、磁盘满、内存压力。

## 8.8 升级、备份与容灾

### 滚动升级零中断

在线推理服务升级要零中断，靠 Deployment 滚动 + readinessProbe + Service 流量切换：

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0                # 关键：永不少于期望副本数
  template:
    spec:
      containers:
        - name: vllm
          readinessProbe:              # 就绪才接流量
            httpGet: { path: /health, port: 8000 }
            initialDelaySeconds: 30
            periodSeconds: 10
      terminationGracePeriodSeconds: 120   # 给优雅关停（排空连接）留时间
```

配合 `preStop` hook 主动从 Service 摘流 + 应用优雅关停（vLLM 的 `SIGTERM` 处理）。

### etcd 备份（最重要的容灾）

**etcd 是整个集群的脑**。失去 etcd = 失去整个集群状态。生产必须定期备份：

```bash
# 定时快照（cron 每 1-6 小时）
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-$(date +%s).db \
  --endpoints=https://etcd0:2379 \
  --cacert=/etc/etcd/ca.crt \
  --cert=/etc/etcd/server.crt --key=/etc/etcd/server.key

# 验证快照
etcdctl snapshot status /backup/etcd-xxx.db
```

**踩坑**：备份要存到**集群外部**（对象存储），否则集群没了备份也没了。定期做**恢复演练**——很多人备份了几年从没验证过能恢复，真出事才发现备份损坏。

### 版本升级：一次一小步

K8s 版本升级遵循"一次升一个 minor、先升控制平面再升节点、先 dev 再 staging 再 prod"。注意 **API 弃用**：每个 K8s 版本会弃用一批旧 API（如 v1.25 弃 `batch/v1beta1` CronJob，v1.22 弃众多 `extensions/v1beta1`）。升级前用 `kubectl convert` / `pluto` / `kubent`（kube-no-trouble）扫描集群里的弃用资源，先改完再升，否则升级后这些资源直接消失。

## 本章小结

把 K8s 用于 AI 平台的生产实践，可以归结为六件事：**高可用的控制平面**（多副本 apiserver + 5 节点 etcd + 选主 scheduler）、**专用的 GPU 节点池**（污点隔离 + GPU Operator + MIG/MPS 提利用率 + 拓扑感知调度）、**Gang 调度的训练任务**（Volcano/scheduler-plugins/原生 PodGroup + 上层 Training Operator/Ray）、**AI 友好的调度策略**（关 binpack + PriorityClass 体系 + Descheduler 重平衡）、**GPU 利用率为核心的可观测性**（Metrics Server + kube-state-metrics + DCGM-Exporter + Prometheus + 告警）、**最小权限的多租户安全**（RBAC + Kyverno 准入 + NetworkPolicy + ResourceQuota）。故障排查则沿着 Pod 生命周期倒推（Pending→调度、ContainerCreating→运行时网络存储、CrashLoop→应用/OOM、GPU→Device Plugin/runtime）。最后，etcd 备份 + 恢复演练 + 谨慎的版本升级是容灾底线。掌握这些，你的 AI 平台才能在真实生产负载下稳定运行。

**参考来源**

- [NVIDIA GPU Operator 文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/overview.html)
- [Volcano 调度器文档](https://volcano.sh/en/docs/)
- [scheduler-plugins（Coscheduling / NodeResourceTopology）](https://scheduler-plugins.sigs.k8s.io/)
- [Kubeflow Training Operator](https://github.com/kubeflow/training-operator)
- [Kubernetes Descheduler](https://github.com/kubernetes-sigs/descheduler)
- [Kyverno 策略引擎](https://kyverno.io/)
- [kube-no-trouble（kubent）弃用资源检查](https://github.com/doitintl/kube-no-trouble)
- [DCGM-Exporter 与 GPU 监控](https://github.com/NVIDIA/dcgm-exporter)
- [etcd 灾难恢复](https://kubernetes.io/zh-cn/docs/tasks/administer-cluster/configure-upgrade-etcd/)
