# 计算机网络

> 一句话理解：**计算机网络是 AI 基础设施的“血管系统”——数据和梯度通过它在 GPU、CPU、交换机、负载均衡器之间流动；血管不通畅，再强的算力也会缺氧。**

如果你已经理解了 Linux 系统调优，下一步就该把目光投向网络。AI 平台上的大量诡异问题，最终都会追溯到网络：

- 分布式训练 NCCL all-reduce 突然超时，可能是 RoCE 的 PFC/ECN 配置不当、交换机缓冲区不足，或 IRQ 绑定错误；
- LLM 推理服务的 P99 延迟抖动，可能是 DNS 解析慢、负载均衡策略不合理、TCP 拥塞窗口震荡，或容器网卡队列竞争；
- Kubernetes Pod 之间偶发连不上，可能是 CNI 插件、iptables/ipvs、MTU、NetworkPolicy 的某一层出了问题；
- 大模型 checkpoint 保存到对象存储慢，可能是 TCP 窗口、RTT、带宽时延积没有充分利用。

本章面向的是**已经会用 Linux 和 Kubernetes，但想理解网络为什么这样工作**的工程师。

## 学习目标

读完本章，你将能够：

1. 解释 OSI/TCP-IP 分层模型，以及每一层在 AI 工作负载中的作用；
2. 理解分组交换、电路交换、复用、端到端原则、带宽时延积、incast 等核心思想；
3. 理解 TCP 可靠传输、滑动窗口、拥塞控制（Reno/CUBIC/BBR）的基本机制；
4. 理解数据中心网络拓扑：Spine-Leaf、Clos、fat-tree、3D-torus、OCS；
5. 理解 RDMA、InfiniBand、RoCE、NVLink 在分布式训练中的角色和 trade-off；
6. 理解 Kubernetes CNI、Service、kube-proxy、CoreDNS、Ingress/Gateway API 的网络原理；
7. 理解 L4/L7 负载均衡、DNS、服务网格（Istio/Envoy）在 AI 推理服务中的应用；
8. 掌握基础网络排障工具链：ping、traceroute、tcpdump、ss、iperf、nccl-tests；
9. 与 Linux 系统调优、容器运行时、Kubernetes、LLMOps、AI SRE、案例研究主题形成知识闭环。

## 本章与手册其他主题的关系

| 主题 | 关系 | 本章会讲到的交叉点 |
|---|---|---|
| [Linux 系统与性能调优](/01-foundation/linux-systems/) | 下层实现 vs 上层抽象 | Linux 系统调优讲“内核协议栈、NAPI、RPS/RFS/XPS、XDP/RDMA 如何实现”，本章讲“网络协议、拓扑、RDMA/RoCE/IB、CNI/LB/DNS”。 |
| [容器运行时](/02-cloud-native/container-runtime/) | 容器隔离 vs 网络连接 | 容器运行时讲“怎么用 namespace/bridge/veth 做容器网络”，本章讲“bridge/veth/路由表背后的二层/三层网络原理”。 |
| [Kubernetes](/02-cloud-native/kubernetes/) | 编排层 vs 网络层 | Kubernetes 主题讲“CNI/Service/DNS 怎么用”，本章讲“它们背后的网络协议与数据包路径”。 |
| [vLLM / TensorRT-LLM](/04-llmops/) | 推理引擎 vs 网络 | 分布式推理和多机通信依赖 NCCL、RDMA/TCP；本章解释这些网络机制如何影响推理延迟与吞吐。 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 流量入口 vs 网络基础 | Gateway 的负载均衡、DNS、路由、TLS 终止都建立在计算机网络基础之上。 |
| [AI SRE](/07-ai-sre/) | 可观测 vs 网络指标 | 网络延迟、丢包、重传、带宽是 AI SRE 的核心 SLI；本章解释这些指标的含义。 |
| [Meta / Google / OpenAI 案例研究](/09-case-study/) | 超大规模集群 vs 网络设计 | 这些案例研究详细讲数据中心网络、fat-tree、OCS、RoCE/InfiniBand；本章提供理论基础。 |

## 本章结构

按手册统一结构，本章包含 11 节：

1. [背景](01-background) — 为什么 AI Infra 工程师必须懂计算机网络
2. [核心思想](02-core-ideas) — 分层、分组、可靠与拥塞
3. [架构设计](03-architecture) — 数据中心网络与 AI 集群拓扑
4. [网络工作流程](04-network-workflow) — 一个训练/推理包的完整旅程
5. [核心模块](05-core-modules) — NIC、协议栈、CNI、DNS、负载均衡、可观测
6. [源码分析](06-source-analysis) — TCP CUBIC / Cilium eBPF / NCCL 三者选一
7. [工程实践](07-mini-demo) — CPU 可运行网络机制模拟器
8. [企业生产实践](08-production-practice) — RDMA、K8s 网络与 LLM 服务网络调优
9. [最佳实践](09-best-practices) — AI 集群网络设计检查清单
10. [面试题](10-interview-questions) — 初/中/高级计算机网络面试题
11. [延伸阅读](11-further-reading) — 书籍、RFC、论文与官方文档

## 一句话总结

> **计算机网络不是“能 ping 通就行”的管道，而是决定 AI 训练/推理效率、稳定性和成本的关键基础设施。理解它，才能解释为什么同样的代码和硬件，在不同网络环境下会有完全不同的表现。**
