# 11. 延伸阅读

## 官方文档

- [The Linux Kernel Documentation](https://www.kernel.org/doc/html/latest/) — 最权威的内核文档，涵盖 sched、mm、block、networking、cgroup。
- [sched_ext 官方文档](https://docs.kernel.org/scheduler/sched-ext.html) — 用 BPF 写调度器的框架说明与 ABI 约定。
- [scx 调度器仓库](https://github.com/sched-ext/scx) — scx_rusty / scx_layered / scx_bpfland 等生产级 BPF 调度器。
- [Linux man pages](https://man7.org/linux/man-pages/) — 系统调用和库函数手册。
- [systemd 官方文档](https://systemd.io/) — systemd、cgroup 集成、unit 文件。
- [io_uring 官方资料与 liburing](https://github.com/axboe/liburing) — 异步 I/O 用户态库与新特性说明。

## 版本与动态

- [KernelNewbies — Linux 6.17](https://kernelnewbies.org/Linux_6.17) / [Linux 6.18](https://kernelnewbies.org/Linux_6.18) — 每个大版本的新特性盘点（6.18 是 2025-11 发布的最新 LTS）。
- [LWN.net](https://lwn.net/) — 高质量 Linux 内核深度文章，CFS、cgroup v2、memory management、sched_ext 等主题必读。
- [Phoronix Kernel / BPF 板块](https://www.phoronix.com/search/BPF) — 内核开发动态追踪。

## 性能分析

- [Brendan Gregg — Linux Performance](https://www.brendangregg.com/linuxperf.html) — 性能分析方法论、工具图谱、案例。
- [Brendan Gregg — USE Method](https://www.brendangregg.com/usemethod.html) — USE 方法详解。
- 《Systems Performance: Enterprise and the Cloud》 — Brendan Gregg 经典著作。

## eBPF / 动态追踪

- [BPF Performance Tools](https://www.brendangregg.com/bpf-performance-tools-book.html) — Brendan Gregg 的 eBPF 工具书。
- [bcc 工具集](https://github.com/iovisor/bcc) — Python/C 编写的 eBPF 工具。
- [bpftrace](https://github.com/iovisor/bpftrace) — 高级追踪脚本语言。
- [eBPF Applications Landscape](https://ebpf.io/applications/) — eBPF 生态全景（Cilium、Beyla、Pixie、Tetragon、Kepler 等）。
- [Grafana Beyla 与 OpenTelemetry eBPF](https://grafana.com/oss/beyla/) — 零代码自动埋点。

## GPU 与 AI 场景的 Linux 优化

- [NVIDIA GPUDirect Storage 文档](https://docs.nvidia.com/gpudirect-storage/) — GDS 架构、cuFile API 与部署指南。
- [NVIDIA Magnum IO](https://developer.nvidia.com/magnum-io) — GPUDirect RDMA / GDS / GDRCopy 全家桶。
- [CUDA 文档](https://docs.nvidia.com/cuda/) — CUDA 运行时与 Linux 驱动交互细节（见 [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/)）。

## 相关主题

| 主题 | 链接 | 与本章的关系 |
|---|---|---|
| 容器运行时 | [容器运行时](/02-cloud-native/container-runtime/) | namespace/cgroup/overlayfs 的上层应用 |
| Kubernetes | [Kubernetes](/02-cloud-native/kubernetes/) | K8s 资源限制、QoS 最终通过 Linux cgroup 生效 |
| GPU 架构与 CUDA 基础 | [GPU 架构与 CUDA 基础](/01-foundation/gpu-cuda/) | GPU 驱动、CUDA Runtime 依赖 Linux 的设备文件和模块 |
| AI SRE | [AI SRE](/07-ai-sre/) | CPU/memory/I/O/network 指标都来自 Linux 内核 |
| Ray | [Ray](/03-ai-platform/ray/) | Ray worker 进程和对象存储依赖 Linux 进程调度和 I/O |
| vLLM | [vLLM](/04-llmops/vllm/) | 推理延迟和吞吐受 Linux 调度、内存、网络影响 |

## 推荐学习路径

1. 先读完本章 11 节，建立 Linux 全景；
2. 动手跑 Mini Demo，理解 CFS、LRU、I/O 调度、cgroup；
3. 在真实服务器上练习 `top`、`vmstat`、`iostat`、`mpstat`、`perf`、`bpftrace`；
4. 结合容器运行时和 Kubernetes 主题，理解 cgroup/namespace 的上层抽象；
5. 遇到真实性能问题时，按“先观测、再调优”的方法论逐步深入。

## 一句话总结

> **Linux 内核文档和 Brendan Gregg 的工具书是 AI Infra 工程师的常备参考书；理解了机制，工具只是放大器。**
