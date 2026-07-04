# 11. 延伸阅读

## 11.1 经典书籍

| 书名 | 作者 | 推荐理由 |
|---|---|---|
| 《TCP/IP Illustrated, Volume 1》 | W. Richard Stevens | TCP/IP 协议细节圣经，配合抓包看效果最佳。 |
| 《Computer Networking: A Top-Down Approach》 | Kurose & Ross | 适合快速建立网络全局视角。 |
| 《The Datacenter as a Computer》 | Luiz André Barroso 等 | 数据中心网络与计算融合的经典。 |
| 《Programming Kubernetes》 | 多位作者 | 深入理解 CNI、Service、NetworkPolicy。 |
| 《Linux Kernel Networking》 | Rami Rosen | 内核网络实现，适合想读源码的同学。 |

## 11.2 关键 RFC 与标准

- RFC 793 / RFC 9293 — TCP
- RFC 768 — UDP
- RFC 791 / RFC 8200 — IPv4 / IPv6
- RFC 3168 — ECN
- RFC 7348 — VXLAN
- IEEE 802.1Qbb — PFC
- InfiniBand Architecture Specification
- RDMA Consortium Verbs Specification

## 11.3 官方文档

- [Linux Networking Documentation](https://www.kernel.org/doc/html/latest/networking/index.html)
- [NVIDIA NCCL Documentation](https://docs.nvidia.com/deeplearning/nccl/)
- [NVIDIA RDMA/RoCE Configuration Guide](https://docs.nvidia.com/networking/)
- [Cilium Documentation](https://docs.cilium.io/)
- [Kubernetes Networking Concepts](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [Istio / Envoy Documentation](https://istio.io/latest/docs/)

## 11.4 论文与工业界分享

| 主题 | 推荐材料 |
|---|---|
| Google 数据中心网络 | Jupiter Rising、NSDI'24 双路径恢复论文、Falcon 相关演讲 |
| Meta AI 网络 | Meta 关于 RoCE 与 InfiniBand 双织物网络的博客与论文 |
| OpenAI 训练集群 | 关于 Infiniband 大规模集群的演讲与采访 |
| 拥塞控制 | DCTCP (SIGCOMM 2010)、BBR (ACM Queue 2016) |
| 集合通信 | Bandwidth-Optimal All-reduce Algorithms、NCCL 论文 |
| 可编程网络 | P4、SmartNIC、In-network Aggregation |

## 11.5 本手册相关主题

- [Linux 系统与性能调优](../linux-systems/)：网络协议栈、NAPI、RPS/RFS/XPS、XDP/DPDK。
- [容器运行时](../../02-cloud-native/container-runtime/)：网络 namespace、veth、bridge、CNI 调用链。
- [Kubernetes](../../02-cloud-native/kubernetes/)：Service、kube-proxy、CoreDNS、Ingress/Gateway API。
- [vLLM](../../04-llmops/vllm/)：分布式推理中的 NCCL 与网络。
- [TensorRT-LLM](../../04-llmops/tensorrt-llm/)：多机 TP/PP 的网络拓扑。
- [Triton Inference Server](../../04-llmops/triton/)：gRPC/HTTP 入口网络。
- [LLM Gateway](../../04-llmops/llm-gateway/)：负载均衡、路由、限流。
- [AI SRE](../../07-ai-sre/)：网络监控、SLO、故障演练。
- [案例研究：Meta](../../09-case-study/meta/)：RoCE 与 InfiniBand 双织物。
- [案例研究：Google](../../09-case-study/google/)：OCS、3D-torus、Falcon。
- [案例研究：OpenAI](../../09-case-study/openai/)：大规模训练 InfiniBand 网络。

## 11.6 社区与会议

- ACM SIGCOMM / NSDI / EuroSys：网络与系统顶会。
- NVIDIA GTC：NCCL、RDMA、AI 网络最佳实践。
- KubeCon + CloudNativeCon：Cilium、eBPF、Gateway API。
- Linux Plumbers Conference：内核网络、eBPF、RDMA。

## 11.7 一句话收尾

计算机网络不是“连上线就行”，而是 AI Infra 的**性能底座**和**稳定性底座**。理解它，是做出可扩展、可运维、可排障的 AI 系统的关键一步。
