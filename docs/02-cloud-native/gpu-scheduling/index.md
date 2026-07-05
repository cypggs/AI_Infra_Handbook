# GPU 调度与资源管理总览

> 一句话理解：**GPU 在 Kubernetes 上不是“有 CPU 就行”的普通资源，而是需要设备发现、切分、拓扑感知、Gang 与队列调度的异构资源**——K8s 通过 Device Plugin 把物理 GPU 映射成 `nvidia.com/gpu`，通过调度框架扩展点把“卡数、显存、NVLink、MIG、队列”纳入决策，最终让训练/推理 Pod 既抢得到卡、又不浪费卡、还能公平共享集群。

## 为什么 AI 平台工程师必须懂 GPU 调度

不懂 GPU 调度的 AI 平台工程师，很容易把集群建成“有卡但调不动、多租户互相抢、训练一扩就崩”的状态。典型场景：

- 一个 8 卡分布式训练 Job 只启动了 7 个 worker，剩下 1 个永远等不到卡，整个 Job 白跑——这是 **Gang 调度**缺失导致的 all-or-nothing 失败。
- 128 卡训练在 64 卡规模下正常，扩到 128 卡后 NCCL all-reduce 性能断崖下降——这是 **拓扑感知调度**没把 NVLink/PCIe/NIC 亲和性考虑进去。
- 推理服务为了省成本把 4 个 Pod 塞到同一张卡上，结果某个 Pod 的 KV Cache 把显存撑爆，全部实例 OOM——这是 **GPU 切分与隔离模型**选错了。
- 多租户集群里，A 团队的大训练 Job 把卡占满，B 团队的推理服务永远 Pending——这是缺少 **队列与公平调度**。
- Pod 调度到节点后，kubelet 报 `UnexpectedAdmissionError`，`nvidia-smi` 看不到卡——这是 **Device Plugin 与节点组件生命周期**出了问题。

这些都不是“加几台 GPU 机器”能解决的。理解 K8s 上的 GPU 资源模型、调度扩展点、设备插件机制和队列调度器，是设计生产级 AI 平台的必修课。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释 K8s 扩展资源模型：`nvidia.com/gpu` 是怎么从物理 GPU 变成 Pod 里的 `requests/limits` 的。
2. 对比 MIG、MPS、time-slicing、vGPU 四种 GPU 切分/共享机制的隔离级别与适用场景。
3. 画出 GPU Pod 从创建到 Running 的完整链路：Device Plugin 注册 → scheduler Filter/Score → kubelet Allocate → 容器启动 → 健康检查 → 释放。
4. 说清调度框架的扩展点（Filter/Score/Reserve/Permit/Bind/PostBind）如何被 GPU 相关插件使用。
5. 比较 scheduler-plugins（Coscheduling / NodeResourceTopology / CapacityScheduling）、Volcano、Kueue 三种主流方案的定位与取舍。
6. 读懂 NVIDIA Device Plugin、GPU Operator、scheduler-plugins、Volcano 的核心源码调用链。
7. 在生产中排查典型故障：Pod 卡在 Pending、UnexpectedAdmissionError、MIG 配置不生效、队列饿死、拓扑性能差。
8. 回答初 / 中 / 高级 GPU 调度面试题，能把资源模型、调度语义与源码联系起来。

## GPU 调度与其他主题的关系

| 主题 | 解决的核心问题 | 与 GPU 调度的关系 |
|---|---|---|
| [Foundation](/01-foundation/) | Linux / 网络 / 存储 / GPU 硬件基础 | GPU 调度的底层是 PCIe、NUMA、NVLink、CUDA；Device Plugin 最终把 `/dev/nvidia*` 透传给容器 |
| [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) | GPU 硬件架构、CUDA 编程模型、NVIDIA 软件栈 | MIG/MPS/显存墙/Compute Capability 等概念由该主题展开；本主题聚焦如何把这些能力调度到 K8s |
| [Kubernetes](/02-cloud-native/kubernetes/) | 声明式编排、调度框架、资源模型 | GPU 调度是 K8s 调度框架与 Device Plugin 扩展点的具体应用；通用调度语义见该主题 |
| [容器运行时](/02-cloud-native/container-runtime/) | 镜像管理 + 容器生命周期 | Containerd / CRI-O 在创建容器时接收 kubelet 传入的设备节点与环境变量 |
| [CNI / CSI 深度](/02-cloud-native/cni-csi/) | 网络与存储插件接口 | RDMA 网络、多网卡、高速存储是 GPU 训练 Pod 的性能底座 |
| [Operator 模式](/02-cloud-native/operator/) | CRD + Controller 持续调和 | NVIDIA GPU Operator 就是典型 Operator；本主题会分析它的组件编排 |
| **GPU 调度与资源管理** | 把 GPU 引入 K8s 调度与治理 | 本主题 |
| [Ray](/03-ai-platform/ray/) | 分布式 Python 计算 | Ray on K8s 的 worker 需要 GPU 资源声明；训练/推理任务依赖本主题的资源模型 |
| [vLLM](/04-llmops/vllm/) / [TensorRT-LLM](/04-llmops/tensorrt-llm/) | 单实例推理引擎 | 生产部署时通过 K8s Deployment/StatefulSet 声明 GPU，依赖 time-slicing/MPS/多卡调度 |
| [AI SRE](/07-ai-sre/) | 可观测、SLO | DCGM-Exporter、GPU 利用率、显存、温度、NCCL 指标是 AI 平台监控核心 |
| [安全](/08-security/) | IAM、多租户隔离 | GPU 集群的多租户隔离不仅是 RBAC，还包括队列配额、MIG 硬隔离、NetworkPolicy |

## 本章结构

1. [背景](01-background) — 从 AI 训练/推理的 all-or-nothing、显存墙、拓扑敏感、多租户公平性出发，解释原生 K8s 调度为何不够。
2. [核心思想](02-core-ideas) — extended resource、`nvidia.com/gpu` 资源模型、MIG/MPS/time-slicing/vGPU 语义对比、Device Plugin 抽象、拓扑感知、Gang、队列公平调度。
3. [架构设计](03-architecture) — 从 Pod 创建到 GPU 分配的全景架构：kubelet device-manager ↔ Device Plugin gRPC、scheduler framework 扩展点、GPU Operator 组件编排、Volcano/Kueue/scheduler-plugins 在控制平面中的位置。
4. [调度工作流程](04-scheduling-workflow) — 以时序/状态机追踪 GPU Pod 完整旅程：ListAndWatch → Filter/Score/Reserve/Permit/Bind → Allocate/PreStartContainer → 容器启动 → 健康检查 → 释放回收。
5. [核心模块](05-core-modules) — 深入 NVIDIA Device Plugin、GPU Operator、scheduler-plugins、Volcano、Kueue。
6. [源码分析](06-source-analysis) — NVIDIA k8s-device-plugin、GPU Operator、scheduler-plugins coscheduling/noderesourcetopology、Volcano scheduler 主干源码调用链。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的 GPU 调度概念模拟器（后续补充）。
8. [企业生产实践](08-production-practice) — AI 集群 GPU 调度选型、典型故障、性能调优、多租户隔离。
9. [最佳实践](09-best-practices) — GPU 调度检查清单、AI 负载特化、YAML 模板。
10. [面试题](10-interview-questions) — 初 / 中 / 高级 GPU 调度面试题。
11. [延伸阅读](11-further-reading) — 官方文档、KEP、源码、论文与学习路径。

## 一句话总结

GPU 调度的精髓在于**“把物理 GPU 的异构能力翻译成 K8s 可调度、可切分、可治理的资源语义”**：Device Plugin 负责“看见卡”，GPU Operator 负责“管好节点组件”，scheduler-plugins / Volcano / Kueue 负责“按 AI 负载规则排队和选址”；对 AI 平台而言，选对切分模型决定利用率，选对调度器决定公平性与扩展性，理解源码与调用链决定排障效率——三者共同决定一张昂贵的 GPU 卡能不能在集群里物尽其用。
