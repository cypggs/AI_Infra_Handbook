# 11. 延伸阅读与学习路径

> 一句话理解：**GPU 调度的深度来自“读 Device Plugin 规范、读 NVIDIA 官方文档、读 Volcano/Kueue/scheduler-plugins 源码、读生产排障案例”四件事**。

## 11.1 官方文档（按优先级）

### Kubernetes 设备插件与 GPU

| 优先级 | 文档 | 读什么 |
|---|---|---|
| **P0** | [Kubernetes Device Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/) | Device Plugin 协议、ListAndWatch/Allocate 语义 |
| **P0** | [NVIDIA GPU Operator 文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html) | 安装、升级、MIG、可观测 |
| **P1** | [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin) | 源码、MIG 支持、time-slicing 配置 |
| **P1** | [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/) | 容器运行时集成、libnvidia-container |
| **P2** | [NVIDIA MIG 用户指南](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/) | MIG profile、NCCL 限制、生产建议 |

### 调度框架与队列

| 优先级 | 文档 | 读什么 |
|---|---|---|
| **P0** | [Kubernetes Scheduler Framework](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/) | Filter/Score/Reserve/Permit/PreBind 扩展点 |
| **P1** | [scheduler-plugins](https://github.com/kubernetes-sigs/scheduler-plugins) | NodeResourceTopology、Coscheduling / Gang |
| **P1** | [Volcano 文档](https://volcano.sh/en/docs/) | PodGroup、Queue、Job 调度 |
| **P1** | [Kueue 文档](https://kueue.sigs.k8s.io/docs/) | ClusterQueue、LocalQueue、Workload、AdmissionCheck |
| **P2** | [KEP 624: Scheduling Framework](https://github.com/kubernetes/enhancements/tree/master/keps/sig-scheduling/624-scheduling-framework) | 调度框架设计演进 |

## 11.2 规范与源码仓库

### Device Plugin 与 GPU 生态

| 仓库 | 读什么 |
|---|---|
| [kubernetes/kubernetes/pkg/kubelet/cm/devicemanager](https://github.com/kubernetes/kubernetes/tree/master/pkg/kubelet/cm/devicemanager) | kubelet 端 Device Plugin 管理 |
| [NVIDIA/k8s-device-plugin](https://github.com/NVIDIA/k8s-device-plugin) | NVIDIA Device Plugin 完整实现 |
| [NVIDIA/gpu-operator](https://github.com/NVIDIA/gpu-operator) | GPU Operator Helm chart 与组件编排 |
| [NVIDIA/dcgm-exporter](https://github.com/NVIDIA/dcgm-exporter) | GPU 指标暴露 |
| [NVIDIA/node-feature-discovery](https://github.com/NVIDIA/node-feature-discovery) | GPU 与拓扑标签发现 |
| [NVIDIA/gpu-feature-discovery](https://github.com/NVIDIA/gpu-feature-discovery) | GPU 型号与 MIG 标签 |

### 调度器与队列

| 仓库 | 读什么 |
|---|---|
| [kubernetes-sigs/scheduler-plugins](https://github.com/kubernetes-sigs/scheduler-plugins) | NodeResourceTopology、Coscheduling 插件 |
| [volcano-sh/volcano](https://github.com/volcano-sh/volcano) | Gang 调度、Queue、Preemption |
| [kubernetes-sigs/kueue](https://github.com/kubernetes-sigs/kueue) | 工作负载队列与资源管理 |
| [kubernetes/kubernetes/pkg/scheduler](https://github.com/kubernetes/kubernetes/tree/master/pkg/scheduler) | 默认调度器框架与算法 |

## 11.3 经典演讲与论文

| 资源 | 为什么读 |
|---|---|
| [NVIDIA GPU Operator: Life of a GPU Node](https://www.youtube.com/c/NVIDIA) | 理解 GPU Operator 组件协同与 Day-2 运维 |
| [GPUDirect RDMA 文档](https://docs.nvidia.com/cuda/gpudirect-rdma/) | RDMA 与 GPU 直接通信的硬件基础 |
| [NCCL 调优指南](https://docs.nvidia.com/deeplearning/nccl/) | 训练通信参数与网络配置对应关系 |
| [Kubernetes SIG-Scheduling 演讲](https://www.youtube.com/c/KubernetesCommunity) | 调度框架、多租户、资源配额演进 |
| [Volcano: A Kubernetes Native Batch System](https://volcano.sh/) | 了解 Volcano 设计动机与生态 |
| [Kueue: Kubernetes-native Job Queueing](https://kueue.sigs.k8s.io/) | 了解 Kueue 与原生 scheduler 的协作模式 |

## 11.4 生产实践与案例

| 资源 | 读什么 |
|---|---|
| [NVIDIA GPU Operator 最佳实践](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html) | 安装、升级、MIG、Troubleshooting |
| [AWS EKS GPU 节点文档](https://docs.aws.amazon.com/eks/latest/userguide/gpu-ami.html) | 云上 GPU 节点与 Device Plugin 实践 |
| [GKE GPU 文档](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus) | GKE 上的 GPU 调度与 MIG |
| [Azure AKS GPU 节点](https://learn.microsoft.com/en-us/azure/aks/gpu-cluster) | Azure 上 GPU Operator 部署 |
| [NVIDIA GPU Cloud (NGC)](https://catalog.ngc.nvidia.com/) | 官方优化镜像与 Helm chart |

## 11.5 与本手册其他主题的交叉引用

| 主题 | 与本主题的衔接 | 阅读建议 |
|---|---|---|
| [Kubernetes](/02-cloud-native/kubernetes/) | Device Plugin、kube-scheduler、ResourceQuota 都建立在 K8s 基础上 | 先读 K8s 主题，再深入 GPU 调度 |
| [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) | 理解 GPU 拓扑、NVLink、NCCL、显存 | 本主题讲“怎么调度”，gpu-cuda 讲“GPU 是什么” |
| [容器运行时](/02-cloud-native/container-runtime/) | NVIDIA Container Toolkit 依赖 container runtime | 读运行时理解 GPU 设备如何挂载到容器 |
| [Operator](/02-cloud-native/operator/) | GPU Operator 本身就是一个大型 Operator | 读 Operator 主题理解其控制循环与升级逻辑 |
| [vLLM](/04-llmops/vllm/) | GPU 调度直接决定 vLLM 服务的吞吐与延迟 | 结合本主题做推理 placement 设计 |
| [TensorRT-LLM](/04-llmops/tensorrt-llm/) | TensorRT-LLM 推理需要显存与 batch 策略匹配 | 按模型显存选 MIG profile 或整卡 |
| [KubeRay](/03-ai-platform/kuberay/) | Ray on K8s 需要 GPU 资源与 Gang 调度 | 结合 Kueue/Volcano 做 Ray 集群调度 |
| [计算机网络](/01-foundation/computer-networks/) | RDMA/RoCE/IB 是千卡训练网络基础 | 本主题讲“如何与 GPU 配合”，网络主题讲“为什么” |
| [AI SRE](/07-ai-sre/) | GPU 可观测与故障响应是 SRE 核心 | DCGM 指标、Xid 告警、容量规划 |

## 11.6 推荐学习路径

### 路径 A：从 Device Plugin 入手

```text
1. 读 Kubernetes Device Plugins 官方文档（P0）
2. 通读 NVIDIA k8s-device-plugin 源码
3. 用 kind 或 minikube 手动部署 NVIDIA Device Plugin
4. 观察 ListAndWatch 与 Allocate 的 gRPC 调用
5. 配置 time-slicing，观察多 Pod 共享 GPU
6. 阅读 GPU Operator 源码，理解组件编排
```

### 路径 B：从调度器入手

```text
1. 读 Kubernetes Scheduler Framework（P0）
2. 部署 scheduler-plugins，开启 Coscheduling / NodeResourceTopology
3. 对比 Volcano 与 Kueue 的队列语义
4. 用 Kueue 配置 ClusterQueue + LocalQueue + Workload
5. 用 Volcano 配置 Queue + PodGroup
6. 设计一个多租户训练平台的队列模型
```

### 路径 C：AI 平台全栈

```text
1. 先读完 [Kubernetes](/02-cloud-native/kubernetes/) 与 [gpu-cuda](/01-foundation/gpu-cuda/)
2. 读本主题 1-5 章建立 GPU 调度全链路认知
3. 跑通本主题 Mini Demo（gpu-scheduling-mini）
4. 在真实集群或云上部署 GPU Operator + Volcano/Kueue
5. 模拟 MIG 变更、Pod Pending、NCCL timeout 并排障
6. 回看源码（k8s-device-plugin、scheduler-plugins、Kueue）加深理解
```

## 11.7 本章小结

| 类型 | 重点资源 |
|---|---|
| 官方文档 | K8s Device Plugins、NVIDIA GPU Operator、MIG 用户指南 |
| 源码 | k8s-device-plugin、GPU Operator、scheduler-plugins、Volcano、Kueue |
| 演讲论文 | GPU Operator 生命周期、GPUDirect RDMA、NCCL 调优、Kueue/Volcano 设计 |
| 生产实践 | 云厂商 GPU 节点文档、NGC、DCGM 监控 |
| 交叉主题 | Kubernetes、gpu-cuda、容器运行时、Operator、vLLM、TensorRT-LLM、KubeRay、AI SRE |

GPU 调度主题到此结束。建议结合真实 GPU 集群实验，把 Device Plugin 协议、切分技术差异、拓扑感知、队列设计、生产排障内化为肌肉记忆。
