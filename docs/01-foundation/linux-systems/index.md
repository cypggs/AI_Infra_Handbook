# Linux 系统与性能调优

> 一句话理解：**Linux 是 AI Infra 的“地面”——无论你跑的是 Kubernetes、Ray、vLLM 还是大模型训练框架，最终都要落在这片地面上；不懂地面怎么承重，房子建再高也会晃。**

如果你已经了解了 GPU/CUDA 的硬件世界，下一步就该回到软件层面：操作系统。AI 平台上的每一个诡异问题，最终几乎都会追溯到 Linux：

- 训练任务明明 GPU 利用率 100%，为什么整体进度还是慢？可能是 CPU 调度、I/O 等待或 NUMA 不均衡；
- 模型推理 latency 偶尔抖动？可能是 CPU 抢占、内核态开销或 cgroup 限制；
- 容器里某个进程被 OOM Kill？需要理解 Linux 的内存回收、OOM score 和 cgroup limit；
- 分布式训练 NCCL 超时？可能和 IRQ affinity、网络中断处理、内核参数有关。

本章面向的是**已经会用 Linux，但想理解它为什么这样工作**的工程师。

## 学习目标

读完本章，你将能够：

1. 解释 Linux 内核与用户空间的边界，以及系统调用的完整流程；
2. 理解进程/线程/协程、CFS 调度器、nice/RT 调度、CPU 亲和性的工作机制；
3. 理解虚拟内存、页表、TLB、HugePages、NUMA、swap、page cache 的协作方式；
4. 理解 VFS、ext4/xfs、块层、I/O 调度器、page cache 与 direct I/O 的差异；
5. 理解 cgroup v1/v2、namespace 在资源隔离与限制中的作用；
6. 掌握 Linux 性能分析的基本工具链：top、vmstat、iostat、mpstat、perf、bpftrace；
7. 在 AI 训练/推理场景中做基础的系统调优：NUMA 绑定、HugePages、IRQ affinity、kernel boot params；
8. 与容器运行时、Kubernetes、AI SRE 主题形成知识闭环。

## 本章与手册其他主题的关系

| 主题 | 关系 | 本章会讲到的交叉点 |
|---|---|---|
| [容器运行时](/02-cloud-native/container-runtime/) | 下层实现 vs 上层抽象 | 容器运行时讲“怎么用 namespace/cgroup/overlayfs 做容器”，本章讲“这些机制在内核里如何实现、对性能有什么影响”。 |
| [Kubernetes](/02-cloud-native/kubernetes/) | 编排层 vs OS 层 | K8s 的 CPU/memory 限制、QoS、Device Plugin 最终都要通过 Linux cgroup 生效；本章解释 kubelet 写完 `cpu.cfs_quota_us` 后内核做了什么。 |
| [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) | 硬件 vs 系统软件 | GPU 驱动、CUDA Runtime、nvidia-container-toolkit 都依赖 Linux 的模块、设备文件、cgroup；本章解释它们如何协作。 |
| [Ray / KubeRay](/03-ai-platform/ray/) | 分布式运行时 vs OS | Ray 的 worker 进程、对象存储、spillback 都依赖 Linux 进程调度和 I/O 子系统。 |
| [vLLM / TensorRT-LLM](/04-llmops/) | 推理引擎 vs OS | 推理服务的延迟、吞吐、稳定性受 Linux 调度、内存、网络影响。 |
| [计算机网络](/01-foundation/computer-networks/) | OS 网络栈 vs 网络协议 | Linux 系统调优讲“内核协议栈、NAPI、RPS/RFS/XPS、XDP/RDMA 如何实现”，计算机网络讲“网络协议、拓扑、RDMA/RoCE/IB、CNI/LB/DNS”。 |
| [AI SRE](/07-ai-sre/) | 可观测 vs 底层指标 | CPU、memory、I/O、network 指标都来自 Linux 内核；本章解释这些指标的含义。 |

## 本章结构

按手册统一结构，本章包含 11 节：

1. [背景](01-background) — 为什么 AI Infra 工程师必须懂 Linux
2. [核心思想](02-core-ideas) — Kernel/User Space、系统调用、进程模型
3. [架构设计](03-architecture) — Linux 内核整体架构
4. [进程与系统调用](04-process-and-syscall) — 进程生命周期与调度
5. [核心模块](05-core-modules) — CPU、内存、I/O、网络、cgroup、namespace
6. [源码分析](06-source-analysis) — 一个系统调用的完整链路
7. [工程实践](07-mini-demo) — CPU 可运行的 Linux 机制模拟器
8. [企业生产实践](08-production-practice) — AI 场景的 Linux 调优与排障
9. [最佳实践](09-best-practices) — 性能分析方法论
10. [面试题](10-interview-questions) — 初/中/高级 Linux 面试题
11. [延伸阅读](11-further-reading) — 官方文档、书籍、LWN、BPF

## 一句话总结

> **Linux 不是“会用就行”的工具，而是 AI Infra 的底盘。理解它，才能解释为什么同样的硬件、同样的代码，在不同节点上会有完全不同的表现。**
