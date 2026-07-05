# 9. 最佳实践

> 一句话理解：**GPU 调度的最佳实践，是把“切分策略选对、资源边界守好、拓扑信息用好、队列公平可调、故障可观测可回滚”这五件事变成 checklist**。

## 9.1 MIG 配置决策树

```text
工作负载是否需要 GPU 级 QoS 与故障隔离？
  ├─ 是 → 是否需要 NCCL 跨实例通信？
  │         ├─ 是 → 整卡或同一 GPU 上的 MIG 实例（注意 NCCL 限制）
  │         └─ 否 → 使用 MIG，按显存需求选 profile
  │                    ├─ 10 GB → mig-1g.10gb
  │                    ├─ 20 GB → mig-2g.20gb
  │                    ├─ 40 GB → mig-3g.40gb
  │                    └─ 需要接近整卡 → mig-7g.80gb
  └─ 否 → 考虑 MPS / time-slicing（无物理隔离，成本低）
```

### MIG 配置原则

- **不要混用 profile**：同一节点上的所有 GPU 最好使用同一种 MIG profile，避免资源碎片和调度复杂度。
- **训练优先整卡或最大 MIG**：NCCL 对 MIG 支持有限，分布式训练通常仍选整卡。
- **推理按模型显存选 profile**：为每个模型版本建立推荐 MIG profile，写入模型仓库元数据。
- **节点标签必须准确**：NFD / GFD 会暴露 `nvidia.com/gpu.product` 和 MIG 相关标签，调度依赖这些标签。

### MIG ConfigMap 示例

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mig-config
  namespace: gpu-operator
data:
  config.yaml: |
    version: v1
    mig-configs:
      all-3g40gb:
        - devices: all
          mig-enabled: true
          mig-devices:
            "3g.40gb": 2
```

## 9.2 MPS / time-slicing 启用条件

| 技术 | 隔离级别 | 适用场景 | 不推荐场景 |
|---|---|---|---|
| MPS | 进程级共享，显存隔离弱 | 小 batch 推理、开发测试 | 多租户生产、关键推理 |
| time-slicing | 内核级分时，上下文切换开销 | 低优先级批处理、Jupyter 开发 | latency-sensitive 在线推理 |
| MIG | 硬件级实例隔离 | 多租户生产推理 | 需要 NCCL 的分布式训练 |
| 整卡 | 完全独占 | 训练、关键推理 | 显存利用率低的轻量任务 |

### 启用 checklist

- [ ] 已评估进程崩溃对同 GPU 其他任务的影响。
- [ ] 已设置显存上限，避免一个任务吃掉全部显存。
- [ ] 已配置 monitoring，监控 GPU 利用率、显存、上下文切换次数。
- [ ] 在线推理优先用 MIG；仅在成本压力极大且可接受抖动时用 MPS/time-slicing。

## 9.3 拓扑感知注解与调度

### 关键节点标签

| 标签 | 含义 | 用途 |
|---|---|---|
| `nvidia.com/gpu.product` | GPU 型号 | 避免把 A100 任务调度到 H100 节点 |
| `nvidia.com/gpu.memory` | 单卡显存 | 大模型按显存筛选节点 |
| `node.kubernetes.io/instance-type` | 机型 | 与 ResourceQuota/Queue 配合 |
| `topology.kubernetes.io/zone` | 可用区 | 避免跨 AZ 的 RDMA / 存储挂载 |
| NFD PCI/NUMA 标签 | GPU-NIC-CPU 拓扑 | scheduler-plugins 拓扑感知 |

### 拓扑感知 Pod 示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: train-worker
  annotations:
    # scheduler-plugins NodeResourceTopology 使用
    topology.node.k8s.io/rack: rack-01
spec:
  containers:
    - name: train
      image: nvidia/pytorch:24.06-py3
      resources:
        limits:
          nvidia.com/gpu: 8
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: nvidia.com/gpu.product
                operator: In
                values: ["NVIDIA-A100-SXM4-80GB"]
              - key: topology.kubernetes.io/zone
                operator: In
                values: ["zone-a"]
```

### 推荐拓扑策略

- **同节点内满卡**：优先把 8 卡 Pod 调度到同一节点，避免跨节点 NCCL。
- **同 NUMA**：单节点多卡时，选择与 CPU、NIC 同 NUMA 的 GPU。
- **同 NVSwitch 域**：DGX 内部 8 卡通常全互联，不存在域内差异；多 HGX 拼接时注意域边界。
- **同机架**：多机训练时，优先调度到同一机架，减少汇聚层网络跳数。

## 9.4 Gang 调度选型矩阵

| 场景 | 推荐方案 | 关键配置 |
|---|---|---|
| 纯 Volcano 生态 | Volcano PodGroup | `minMember`、`queue`、`priorityClassName` |
| 原生 K8s + 训练队列 | Kueue + scheduler-plugins | ClusterQueue、LocalQueue、Workload |
| 已用 Ray / KubeRay | Ray autoscaler + Kueue | 参考 [/03-ai-platform/kuberay/](/03-ai-platform/kuberay/) |
| 需要抢占与回填 | Volcano / Kueue 均可 | 配置 PriorityClass 与 preemption |
| 多框架统一平台 | Kueue | Workload 抽象适配多种计算框架 |

### Gang 调度关键参数

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: train-pg
spec:
  minMember: 4          # 必须同时调度的 Pod 数
  queue: cq-train       # 所属队列
  minResources:         # 最小资源需求
    nvidia.com/gpu: 32
    cpu: "128"
    memory: 512Gi
  priorityClassName: training-critical
```

## 9.5 ResourceQuota / LimitRange / PriorityClass 组合

### 组合模板

```yaml
# 1. 配额：硬上限
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-gpu
  namespace: team-a
spec:
  hard:
    requests.nvidia.com/gpu: 32
    limits.nvidia.com/gpu: 32
    requests.memory: 512Gi
    pods: 100
---
# 2. 默认值：防止用户漏写
apiVersion: v1
kind: LimitRange
metadata:
  name: team-a-defaults
  namespace: team-a
spec:
  limits:
    - max:
        nvidia.com/gpu: 8
      default:
        nvidia.com/gpu: 1
      defaultRequest:
        nvidia.com/gpu: 1
      type: Container
---
# 3. 优先级：保障关键训练
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: training-critical
value: 1000000
preemptionPolicy: PreemptLowerPriority
---
# 4. 限流：防止单个用户占满队列
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: team-a-train
spec:
  weight: 5
  capability:
    cpu: 256
    memory: 1024Gi
    nvidia.com/gpu: 32
```

### 多租户设计建议

- 每个团队一个 namespace，一个 ResourceQuota。
- 训练、推理、开发分别设置 Queue 或 ClusterQueue，权重按业务价值分配。
- PriorityClass 数量控制在 3-5 个，避免过度抢占导致系统抖动。
- 对开发测试 Queue 设置 borrow limit，防止挤占生产资源。

## 9.6 可观测指标与告警

### 核心指标

| 层级 | 指标 | 采集源 | 告警阈值建议 |
|---|---|---|---|
| 调度 | GPU 分配率、Pending Pod 数、Queue 等待时间 | kube-state-metrics、Volcano/Kueue metrics | Pending > 30min / 队列堆积 |
| 硬件 | GPU 利用率、显存使用率、温度、功耗 | DCGM Exporter | 显存 > 90% / 温度 > 85°C |
| 错误 | Xid 错误码、ECC 错误、掉卡事件 | DCGM Exporter、节点 dmesg | Xid != 0 即告警 |
| 网络 | IB/RoCE 端口错误、带宽、重传 | Node Exporter + IB 厂商工具 | 重传率 > 1% |
| 训练 | NCCL 超时、step 时间抖动 | 应用日志 / exporter | step time > 基线 20% |

### 推荐告警规则（PromQL 示例）

```promql
# GPU 显存使用超过 90%
DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_FREE > 0.9

# Xid 错误
DCGM_FI_DEV_XID_ERRORS > 0

# 节点上可用 GPU 突然变少（掉卡）
(
  kube_node_status_allocatable{resource="nvidia.com/gpu"}
  -
  kube_node_status_capacity{resource="nvidia.com/gpu"}
) != 0

# Pod 长时间 Pending
kube_pod_status_phase{phase="Pending"} == 1
  and on(pod, namespace) (
    time() - kube_pod_start_time > 1800
  )
```

### 可观测 checklist

- [ ] DCGM Exporter 已在所有 GPU 节点运行。
- [ ] GPU 利用率、显存、温度、Xid 已接入 Prometheus/Grafana。
- [ ] Volcano / Kueue 的 queue、podgroup、workload 指标已采集。
- [ ] 训练 Job 已暴露 step time、loss、checkpoint 频率等业务指标。
- [ ] 关键告警已配置 on-call 通道，并区分 P0/P1/P2。

## 9.7 升级与回滚策略

### GPU Operator 升级 checklist

- [ ] 查阅 Release Notes，确认目标版本支持的 K8s / kernel / containerd 版本。
- [ ] 在测试集群用相同内核版本节点验证安装与训练冒烟。
- [ ] 备份当前 Helm values 与 MIG ConfigMap。
- [ ] 选择维护窗口，先升级非生产节点池。
- [ ] 升级后验证 `nvidia-smi`、Pod 调度、DCGM metrics。
- [ ] 保留旧版本 chart 包，便于 `helm rollback`。

### 回滚步骤

```bash
# 查看历史版本
helm history gpu-operator -n gpu-operator

# 回滚到上一版本
helm rollback gpu-operator <revision> -n gpu-operator

# 如果驱动升级失败，可能需要手动卸载驱动并重启节点
kubectl create -f https://raw.githubusercontent.com/NVIDIA/gpu-operator/main/tools/cleanup/cleanup.yaml
```

### 节点维护窗口

```text
1. cordon 节点
2. drain --ignore-daemonsets --delete-emptydir-data
3. 升级 GPU Operator / 驱动 / MIG profile
4. 重启节点（如需要）
5. uncordon 节点
6. 跑一个 cuda-test Pod 验证
7. 逐步接收训练/推理负载
```

## 9.8 本章小结

| 清单 | 核心动作 |
|---|---|
| MIG | 按显存需求选 profile，避免同一节点混用，训练优先整卡 |
| MPS/time-slicing | 仅用于开发/批处理，在线推理优先 MIG |
| 拓扑感知 | 用 NFD/GFD 标签 + scheduler-plugins 实现同 NUMA/同机架调度 |
| Gang 调度 | Volcano 适合训练生态，Kueue 适合原生 K8s 多租户 |
| 配额组合 | ResourceQuota + LimitRange + PriorityClass + Queue 四层防护 |
| 可观测 | DCGM + queue metrics + 训练业务指标三位一体 |
| 升级回滚 | 测试→备份→滚动→验证→保留回滚版本 |

下一章我们用面试题检验这些知识是否真正掌握。
