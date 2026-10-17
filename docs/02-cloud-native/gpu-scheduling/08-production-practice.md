# 8. 企业生产实践

> 一句话理解：**GPU 集群的生产落地不是“装上 Device Plugin 就能跑”，而是从选型、安装、配额、调度策略到故障排查的完整 Day-0/1/2 闭环**。

## 8.1 Day-0：GPU 选型与集群规划

### 选型矩阵

| 维度 | 训练集群 | 推理集群 | 通用平台 |
|---|---|---|---|
| 首要诉求 | 高显存、高 NVLink 带宽、稳定 NCCL | 高吞吐、低 P99 延迟、成本敏感 | 弹性、可运维、多租户 |
| 推荐 GPU | H100 / GB200 NVL72 / B300（整卡或 MIG） | H100 / L40S / A10 / T4 / RTX Pro 6000 | 按团队预算混合部署 |
| 切分方式 | 整卡、MIG、ComputeDomain 整柜（GB200 NVL72） | MIG、Fractional GPU（KAI/HAMi）、MPS | 按负载动态选择 |
| 网络 | RoCEv2 / InfiniBand + GPUDirect RDMA | 常规 25/100Gbps，可选 RDMA | 与训练/推理共享 |
| 存储 | 本地 NVMe + 并行文件系统 | 只读模型仓库 + 本地缓存 | 分层存储 |

### 整卡 vs MIG 决策

```text
是否需要物理级故障隔离与 QoS 保障？
  ├─ 是 → 训练/大模型推理 → 整卡或 MIG instance
  │          ├─ A100/H100 且需要多租户共享 → MIG
  │          └─ 需要最高 NCCL 带宽 → 整卡 + NVSwitch
  └─ 否 → 中小模型推理/开发测试 → MPS / time-slicing
```

- **整卡**：NCCL 性能最好，故障域最小；但利用率低时成本高。
- **MIG（Multi-Instance GPU）**：A100/H100 上把一张卡切成 1/2/3/4/7 个独立实例，每个实例有独立显存与计算单元，支持按 `nvidia.com/mig-<profile>` 分配。
- **MPS（Multi-Process Service）**：多进程共享一张卡，适合延迟不敏感的小任务；但一个进程崩溃可能影响其他进程。
- **time-slicing**：通过 NVIDIA 调度器让多个容器分时复用 GPU，适合开发测试，**不适合** latency-sensitive 推理。

### 节点拓扑规划

```text
DGX/HGX 节点内部拓扑
├── 8 GPUs
│     └── 通过 NVSwitch / NVLink 全互联
├── 多网卡（IB/RoCE）
│     └── 尽量让每颗 GPU 就近访问 NIC，避免跨 NUMA
└── CPU / 内存
      └── 大模型训练需避免 CPU 内存成为瓶颈
```

建议：

- 训练节点优先选 NVLink + NVSwitch 全互联机型（如 DGX A100/H100、HGX）。
- 记录节点拓扑，供后续 [gpu-topology-scheduler](https://github.com/NVIDIA/gpu-feature-discovery) 或 scheduler-plugins 使用。

## 8.2 Day-1：GPU Operator 安装与升级

### 推荐安装方式

```bash
# 添加 NVIDIA Helm 仓库
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# 安装 GPU Operator（已含 Device Plugin、DCGM Exporter、Node Feature Discovery、MIG Manager 等）
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --set driver.enabled=true \
  --set migManager.enabled=true
```

### GPU Operator 核心组件与职责

| 组件 | 职责 |
|---|---|
| NVIDIA Driver DaemonSet | 在节点编译/加载内核驱动 |
| NVIDIA Container Toolkit | 让容器运行时识别 GPU 设备与库 |
| Device Plugin | 向 kubelet 上报 `nvidia.com/gpu` 资源 |
| DCGM Exporter | 暴露 GPU 利用率、显存、温度、Xid 等 metrics |
| Node Feature Discovery | 给节点打 GPU 型号、MIG 能力等标签 |
| MIG Manager | 按 ConfigMap 切分/重置 MIG profile |
| GPU Feature Discovery | 暴露 `nvidia.com/gpu.product` 等节点标签 |
| Validator | 安装后逐项验证驱动/插件/工具链 |

### 安装后验证清单

```bash
# 1. 节点资源已上报
kubectl describe node <node> | grep nvidia.com/gpu

# 2. Device Plugin Pod 正常
kubectl get pods -n gpu-operator -l app=nvidia-device-plugin-daemonset

# 3. 简单 GPU Pod 能跑起来
kubectl run cuda-test --image=nvidia/cuda:12-base --rm -it -- nvidia-smi

# 4. DCGM metrics 可采集
kubectl port-forward -n gpu-operator svc/dcgm-exporter 9400:9400
curl -s localhost:9400/metrics | grep DCGM_FI_DEV_GPU_UTIL
```

### 升级策略

| 组件 | 升级方式 | 风险点 |
|---|---|---|
| GPU Operator | Helm upgrade，建议小版本逐步升；26.7 起关注 GPUCluster/DRA 新 CR | 驱动版本不兼容会触发节点滚动重启 |
| NVIDIA Driver | 大版本升级需 drain 节点 | 内核版本变化时驱动编译失败 |
| Device Plugin | 滚动升级，注意资源上报中断 | Pod 可能短暂无法调度 |
| DRA Driver（可选） | GPU Operator GPUCluster 或独立 Helm；GPU kubelet plugin 仍 alpha | 与 Device Plugin 双轨并存时避免重复上报资源 |
| DCGM Exporter | 独立升级，通常影响小 | metrics 中断影响告警 |

版本基线建议（2026-10）：

- **新集群直接上 GPU Operator 26.x**：Blackwell（B300/GB300/GB200）支持完整（25.10 起），动态 MIG 配置（26.3），需要 DRA/整柜 NVLink 时升 26.7+（要求 K8s ≥ 1.34.2、驱动 ≥ 580、CDI 运行时）。
- **存量 24.x/25.x 集群**：先升到 25.10.x 拿 Blackwell 支持，再评估 26.x；26.7 的驱动原地重启能力可降低升级窗口。

建议：

- 在测试集群跑训练/推理冒烟测试后再升级生产。
- 升级前记录当前 MIG profile 与节点标签，避免重置后调度失败。
- 大版本升级使用蓝绿节点池，逐步迁移负载。

## 8.3 多租户配额与队列设计

### ResourceQuota + LimitRange + PriorityClass 组合

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-gpu-quota
  namespace: team-a
spec:
  hard:
    requests.nvidia.com/gpu: 16
    limits.nvidia.com/gpu: 16
    pods: 50
---
apiVersion: v1
kind: LimitRange
metadata:
  name: team-a-gpu-defaults
  namespace: team-a
spec:
  limits:
    - default:
        nvidia.com/gpu: 1
      defaultRequest:
        nvidia.com/gpu: 1
      type: Container
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: training-critical
value: 1000000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
```

### 队列设计：Volcano vs Kueue vs KAI

| 维度 | Volcano | Kueue | KAI Scheduler |
|---|---|---|---|
| 核心抽象 | Job、Queue、PodGroup | ClusterQueue、LocalQueue、Workload | Queue（层级）、PodGroup、GPU fraction |
| Gang 调度 | 原生支持 | 依赖 scheduler-plugins / 原生 PodGroup | 原生支持（含层级 PodGroup） |
| 抢占 | 支持 | 支持（配合 PriorityClass） | 支持（可抢占性独立配置） |
| 公平共享 | Queue 内 FIFO + 权重；v1.16 新增 fairshare 插件（使用量衰减） | ClusterQueue 权重、Cohort 借用 | DRF + time-based fairshare + reclamation |
| GPU fraction | 需配合 HAMi 等 | 生态方案（如 DRA Consumable Capacity，尚早期） | 原生（HAMi-core 硬隔离） |
| 依赖 | 替换默认 scheduler | 与原生 scheduler 共存 | 独立调度器，可与其它调度器并存 |
| 适用场景 | 大批量训练 Job、HPC | 多租户 AI 平台、训练+推理混合 | GPU 一体集群、推理密度优先 |

注意版本事项：

- **Kueue ≥ v0.20 只保留 v1beta2 API**，升级前必须跑官方迁移脚本转换存量 ClusterQueue/Workload。
- **Volcano 1.15.0/1.15.1 有 DRA 容量记账安全漏洞**，须升到 ≥ 1.15.2。
- K8s 1.37+ 的原生 PodGroup（KEP-4671，Beta）可统一 Gang 语义，但队列与公平共享仍由上述项目提供。

建议：

- 纯训练集群、已用 Volcano 生态 → 继续用 Volcano（v1.16 的命名空间级 Queue 适合平台化）。
- 新建平台、希望与原生 K8s 深度集成 → 选 Kueue。
- GPU 集群要“Gang + fraction + TAS 一步到位” → 评估 KAI Scheduler。

### 命名空间与队列映射

```text
cluster
├── ClusterQueue: cq-train (weight 80)
│     └── LocalQueue: team-a-train, team-b-train
├── ClusterQueue: cq-infer (weight 20)
│     └── LocalQueue: online-infer, offline-batch
└── ClusterQueue: cq-dev (weight 5, borrow limit 10)
      └── LocalQueue: dev-test
```

## 8.4 训练与推理的 placement 策略

### 训练场景

目标： minimize 通信延迟、 maximize NVLink/IB 利用率。

| 策略 | 实现 | 效果 |
|---|---|---|
| 节点内满卡 | `nvidia.com/gpu: 8` 且节点亲和 | 避免跨节点通信 |
| 拓扑感知 | scheduler-plugins `NodeResourceTopology` + NFD 标签 | 选同 NUMA / 同 NVSwitch 域 |
| Gang 调度 | Volcano PodGroup / Kueue Workload | 避免部分 Pod 调度导致的资源死锁 |
| RDMA 亲和 | 把 GPU 与就近 NIC 配对 | 减少跨 NUMA 的 GPUDirect 延迟 |

示例 PodGroup：

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: llm-train-pg
  namespace: team-a
spec:
  minMember: 4
  queue: team-a-train
  priorityClassName: training-critical
```

### 推理场景

目标：高吞吐、低 P99 延迟、快速扩缩容。

| 策略 | 实现 | 效果 |
|---|---|---|
| 单卡多副本 | Deployment `replicas` + HPA | 水平扩展，适合无状态推理 |
| MIG 切片 | 一个节点同时服务多个模型 | 提高显存利用率 |
| Fractional GPU | KAI Scheduler / HAMi 按显存配额切分 | 比 MPS/time-slicing 更安全的中模型混部 |
| PD 分离 | prefill / decode 拆成独立 PodGroup（llm-d + KAI/Kueue Gang） | 两类资源独立伸缩，显著降 TTFT |
| KV Cache 感知路由 | llm-d router（Gateway API） | 请求命中前缀缓存的 decode Pod |
| 节点亲和 + 反亲和 | 同一模型副本分散到不同节点 | 避免单节点故障影响全部 |
| 本地缓存 | initContainer 拉取模型到本地 NVMe | 加速 vLLM / Triton 冷启动 |

2026 年的推理落地范式：**调度器（KAI/Kueue/Volcano）负责把 prefill/decode PodGroup 以 Gang 方式放进拓扑合适的位置，llm-d 负责请求在 Pod 之间的智能路由**。多节点大模型推理（跨机 NVLink 张量并行，如 GB200 NVL72 整柜）则由 DRA ComputeDomain 声明整柜资源。

详细推理部署可参考 [/04-llmops/vllm/](/04-llmops/vllm/) 与 [/04-llmops/tensorrt-llm/](/04-llmops/tensorrt-llm/)。

## 8.5 典型故障与排查

### Pod 调度类

| 现象 | 根因 | 排查 |
|---|---|---|
| Pod 持续 `Pending` | 节点无可用 GPU、MIG profile 不匹配、节点污点 | `kubectl describe pod` / `kubectl describe node` |
| `0/3 nodes are available: 3 Insufficient nvidia.com/gpu` | 资源不足或标签不匹配 | 检查 `nvidia.com/gpu` allocatable |
| Pod 被调度到无 GPU 节点 | Device Plugin 未上报资源或节点标签错误 | `kubectl get node <node> -o yaml` |
| Gang 调度死锁 | 部分 Pod 已调度，部分 Pending | 查看 PodGroup 状态与 queue 资源 |

### 容器启动类

| 现象 | 根因 | 排查 |
|---|---|---|
| `CreateContainerConfigError` | Device Plugin 分配的 device 路径在容器内不可见 | 检查 container runtime + NVIDIA Container Toolkit |
| `nvidia-smi` 在容器内找不到 GPU | 驱动未加载、库挂载失败 | 节点上 `nvidia-smi`、查看 toolkit 日志 |
| OOMKilled | 显存超过 limit 或峰值超过容器可见显存 | 检查 DCGM 显存使用、是否需 MIG 切分 |

### 训练运行类

| 现象 | 根因 | 排查 |
|---|---|---|
| NCCL timeout / hang | 网络不通、MTU 不一致、PFC/ECN 未配、IB 端口 down | `ib_write_bw`、检查 NCCL_DEBUG=INFO |
| 训练 loss 异常 / NaN | 显存 ECC 错误、Xid 48/74/79 | DCGM Xid 告警、换卡重跑 |
| 多机训练速度远低于预期 | GPU-NIC 拓扑不亲和、跨 NUMA、PCIe 瓶颈 | `nvidia-smi topo -m` |

### 节点与硬件类

| 现象 | 根因 | 排查 |
|---|---|---|
| 节点掉卡（GPU 从 `nvidia-smi` 消失） | 硬件故障、PCIe 链路问题、驱动崩溃 | 节点 dmesg、GPU BMC 日志 |
| Xid 95 / 48 / 74 | 通常意味着硬件需要重置或更换 | 标记节点不可调度，隔离后换卡 |
| 温度/功耗告警 | 散热不足、风扇故障 | DCGM 温度指标、机房巡检 |
| GPU Operator Pod CrashLoopBackOff | 驱动与内核版本不匹配、MIG ConfigMap 错误 | 查看 operator validator 日志 |

### 一个真实排障案例：MIG profile 变更导致 Pod Pending

**现象**：team-a 提交了一个请求 `nvidia.com/mig-3g.40gb: 1` 的 Pod，长时间 Pending。

**排查**：

```bash
kubectl describe pod <pod>
# 事件：0/5 nodes are available: 5 Insufficient nvidia.com/mig-3g.40gb

kubectl get node <node> -o json | jq '.status.allocatable | with_entries(select(.key | contains("mig")))'
# 发现节点上只有 nvidia.com/mig-2g.20gb 和 nvidia.com/mig-1g.10gb
```

**根因**：运维人员之前为了 team-b 的开发测试，把节点 MIG profile 改成了 `2g.20gb,1g.10gb`，没有改回训练所需的 `3g.40gb`。

**修复**：

1. 让 team-b 的测试 Pod 退出或迁移到专用测试节点。
2. 修改 MIG Manager ConfigMap，把该节点 profile 改回 `3g.40gb`。
3. 重启该节点 MIG Manager Pod 触发重新切分。
4. 验证节点 allocatable 恢复后重新提交训练任务。

**预防**：

- 不同 MIG profile 的节点用不同节点池/标签，避免混用。
- 训练、推理、开发使用独立 ClusterQueue / Queue。
- 变更 MIG profile 前走审批与影响面评估。

## 8.6 本章小结

| 主题 | 生产要点 |
|---|---|
| 选型 | 训练重 NCCL 与显存（H100/GB200/B300），推理重成本与延迟；MIG/Fraction 适合多租户共享 |
| GPU Operator | 新集群直接 26.x；25.10 拿 Blackwell，26.7 拿 DRA/整柜 NVLink |
| 多租户 | ResourceQuota + LimitRange + PriorityClass + Queue 分层；Kueue ≥ 0.20 注意 v1beta2 迁移 |
| Placement | 训练用 Gang+拓扑感知，推理用 MIG/Fraction+HPA，PD 分离用 llm-d+PodGroup |
| 故障 | 分调度、启动、运行、硬件四层排查，重点关注 Xid 与 NCCL 日志；DRA 1.37 起可对单卡打污点隔离 |

下一章把这些经验固化成可落地的最佳实践与 YAML 模板。
