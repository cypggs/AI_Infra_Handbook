# 9. 最佳实践

> 一句话理解：**CNI / CSI 的最佳实践，是把"接口语义正确、配置可回滚、生命周期可观测、故障可定位"这四件事制度化**——网络侧重点在版本、IPAM、策略和升级；存储侧重点在 sidecar 兼容性、拓扑、RWO 约束、快照和扩容。

## 9.1 CNI 检查清单

### 1. 版本与二进制一致性

- 所有节点的 `/opt/cni/bin` 版本一致；升级时滚动替换并验证 Pod 能正常创建。
- 不要把不同厂商的 CNI 二进制混放，避免配置指向错误插件。

### 2. 配置验证

- 任何 CNI 配置变更前，先用 `cnitool` 或手动 `CNI_COMMAND=ADD` 在测试 netns 验证。
- 保留配置历史，便于回滚。

```bash
# 用 cnitool 验证（需安装 containernetworking/cni 工具）
cnitool add mynet /var/run/netns/test-ns
```

### 3. IPAM 规划

- 每个节点子网大小按最大 Pod 密度设计，预留 20% 余量。
- 生产避免 host-local，改用 Calico IPAM / Cilium IPAM / 控制器集中分配。
- 双栈场景下，IPv4 与 IPv6 地址池都要规划。

### 4. 双栈与 IPv6

```json
{
  "cniVersion": "1.0.0",
  "name": "dual-stack",
  "plugins": [
    {
      "type": "bridge",
      "ipam": {
        "type": "host-local",
        "ranges": [
          [{ "subnet": "10.244.1.0/24" }],
          [{ "subnet": "2001:db8:1::/64" }]
        ]
      }
    }
  ]
}
```

### 5. NetworkPolicy

- 每个 namespace 默认启用 default-deny，再按需放通。
- 放通 DNS：必须允许到 `kube-system/CoreDNS` 的 53/UDP。
- 放通监控：允许 Prometheus / OpenTelemetry 到 Pod metrics 端口。

### 6. 可观测性

- 开启 CNI 日志（Calico felix log、Cilium Hubble）。
- 监控 Pod 创建延迟、CNI ADD 失败率、IP 池使用率。
- 对 SR-IOV 场景，监控 VF 分配与 RDMA 端口状态。

### 7. 升级策略

- CNI 升级前，先在测试集群跑训练 / 推理冒烟测试。
- 升级时采用滚动升级，避免所有 CNI agent 同时重启导致网络中断。
- 升级后检查 NetworkPolicy 是否仍生效。

## 9.2 CSI 检查清单

### 1. sidecar 兼容性

- sidecar 版本与 K8s 版本、CSI spec 版本匹配。
- 常见组合（示例，需按实际版本调整）：

| K8s | external-provisioner | external-attacher | external-resizer | external-snapshotter |
|---|---|---|---|---|
| 1.28 | v4.x | v4.4.x | v1.9.x | v6.3.x |
| 1.29 | v4.x | v4.5.x | v1.10.x | v7.0.x |
| 1.30+ | v5.x | v4.6.x+ | v1.11.x+ | v7.x+ |

### 2. Topology

- 云厂商块存储必须使用 `volumeBindingMode: WaitForFirstConsumer`。
- 多 AZ 集群在 StorageClass `allowedTopologies` 中限制可用区。

### 3. RWO 约束

- 一个 RWO 卷不能同时被两个 Pod 使用，即使它们在同一节点。
- 需要 RWOP（ReadWriteOncePod）时使用 v1.27+ 的 access mode。
- 推理多副本共享模型权重，用 ROX 或 RWX，不要误用 RWO。

### 4. 快照策略

- checkpoint 快照前，确保应用已 flush 数据或文件系统 quiesce。
- 定义清晰的保留策略，避免快照无限累积。
- 定期做快照恢复演练。

### 5. 扩容流程

```text
用户改 PVC spec.resources.requests.storage
   │
   ▼
external-resizer 调用 ControllerExpandVolume
   │
   ▼
底层卷扩容完成，PVC status.capacity 更新
   │
   ▼
Pod 重启或 kubelet rescan 后触发 NodeExpandVolume
   │
   ▼
文件系统扩容完成
```

注意：

- 在线扩容需要 CSI driver 支持 `ONLINE` / `OFFLINE` expand。
- 扩容后必须验证 Pod 内 `df -h` 已变大。

### 6. Driver 升级顺序

1. 升级 CSI driver controller。
2. 升级 CSI node DaemonSet（滚动）。
3. 验证现有卷仍可挂载 / 卸载。
4. 升级 sidecars。

## 9.3 AI 负载特化

### 训练 Job：local SSD + 快照

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: llm-train
spec:
  template:
    spec:
      containers:
        - name: train
          image: llm-train:v1
          resources:
            limits:
              nvidia.com/gpu: 8
          volumeMounts:
            - name: checkpoint
              mountPath: /checkpoints
            - name: dataset
              mountPath: /data
              readOnly: true
      volumes:
        - name: checkpoint
          persistentVolumeClaim:
            claimName: checkpoint-pvc
        - name: dataset
          persistentVolumeClaim:
            claimName: dataset-pvc
            readOnly: true
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node.kubernetes.io/instance-type
                    operator: In
                    values: ["p4d.24xlarge"]
```

### 推理服务：只读 PVC / S3 CSI

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          volumeMounts:
            - name: model
              mountPath: /models
              readOnly: true
      volumes:
        - name: model
          persistentVolumeClaim:
            claimName: model-pvc
            readOnly: true
```

### RDMA：Multus + SR-IOV / Macvlan

```yaml
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  name: rdma-net
  namespace: kube-system
spec:
  config: |
    {
      "cniVersion": "1.0.0",
      "type": "sriov",
      "vlan": 100,
      "ipam": {
        "type": "whereabouts",
        "range": "192.168.100.0/24",
        "gateway": "192.168.100.1"
      }
    }
---
apiVersion: v1
kind: Pod
metadata:
  name: train-worker
  annotations:
    k8s.v1.cni.cncf.io/networks: rdma-net
spec:
  containers:
    - name: train
      image: nvidia/pytorch:24.06-py3
      resources:
        limits:
          nvidia.com/gpu: 8
          sriov/network-attachment-definitions: "1"
```

## 9.4 YAML 模板

### NetworkPolicy：default-deny + allow

```yaml
# 默认拒绝所有 ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: team-a
spec:
  podSelector: {}
  policyTypes: [Ingress]
---
# 允许同 team 且带 app=train 标签的 Pod 互相访问
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-train-team-a
  namespace: team-a
spec:
  podSelector:
    matchLabels: { app: train }
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels: { team: a }
        - podSelector:
            matchLabels: { app: train }
      ports:
        - protocol: TCP
          port: 29500
---
# 允许访问 DNS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: team-a
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels: { k8s-app: kube-dns }
      ports:
        - protocol: UDP
          port: 53
```

### StorageClass：带 topology

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
allowTopologies:
  - matchLabelExpressions:
      - key: topology.ebs.csi.aws.com/zone
        values: ["us-east-1a", "us-east-1b"]
parameters:
  type: gp3
  iops: "16000"
  throughput: "1000"
  encrypted: "true"
reclaimPolicy: Delete
```

### VolumeSnapshot

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: csi-snapclass
driver: ebs.csi.aws.com
parameters:
  tagSpecification_1: "Name=llm-checkpoint"
deletionPolicy: Retain
---
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: checkpoint-snap-20260705
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: checkpoint-pvc
```

## 9.5 本章小结

| 清单 | 核心动作 |
|---|---|
| CNI | 版本一致、配置验证、IPAM 规划、双栈、default-deny、可观测、滚动升级 |
| CSI | sidecar 兼容、topology、RWO/RWOP、快照策略、扩容验证、按序升级 |
| AI 负载 | 训练 local/并行文件系统 + 快照；推理只读 PVC；RDMA Multus + SR-IOV |
| YAML 模板 | NetworkPolicy、StorageClass、VolumeSnapshot 直接可用 |

下一章我们用面试题检验这些知识是否真正掌握。
