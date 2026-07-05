# AI Infra Handbook

面向 AI Infrastructure 工程师的开源中文知识库。

> 目标：打造中文最完整、最系统、最工程化的 AI Infrastructure 学习体系。

[![Deploy](https://img.shields.io/badge/Deploy-Vercel-black?logo=vercel)](https://ai-infra.cypggs.com)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

## 在线阅读

**[https://ai-infra.cypggs.com](https://ai-infra.cypggs.com)**

## 项目定位

这不是博客，不是文章合集，不是官方文档翻译，也不是 AI 总结。

这是一本长期维护的**工程 Handbook**，帮助一名有 Kubernetes / Linux 基础的工程师成长为能够设计和构建 AI 基础设施的平台工程师。

## 目标读者

- AI Infra Engineer
- AI Platform Engineer
- LLMOps Engineer
- AI SRE
- Platform Engineer
- Staff Engineer
- 架构师

## 内容标准

每个主题都按照统一结构执行：

```
Research → Understand → Architecture → Source Code → Engineering Practice
    → Production Experience → Best Practice → Interview → Documentation
```

每个主题包含 11 个章节：

1. 背景
2. 核心思想
3. 架构设计
4. Runtime 工作流程
5. 核心模块
6. 源码分析
7. 工程实践（Mini Demo）
8. 企业生产实践
9. 最佳实践
10. 面试题
11. 延伸阅读

## 目录结构

```
docs/
├── 01-foundation/      # Linux、网络、存储、GPU/CUDA、分布式系统、大模型从 0 到 1
├── 02-cloud-native/    # Docker、Kubernetes、容器运行时、Helm、Operator、CNI/CSI
├── 03-ai-platform/     # Kubeflow、KServe、Ray、MLflow、Airflow
├── 04-llmops/          # vLLM、SGLang、TensorRT-LLM、Triton Inference Server、LLM Gateway
├── 05-agent/           # Agent Runtime、Memory、Multi-Agent、Reflection、MCP、Planning、Tool Use、Agent OS
├── 06-rag/             # Embedding、Retriever、Hybrid Search、GraphRAG
├── 07-ai-sre/          # OpenTelemetry、Observability、AIOps、SLO
├── 08-security/        # IAM、Secrets、Zero Trust、合规
├── 09-case-study/      # OpenAI、Anthropic、Meta、Google、Cursor、Perplexity 等
└── 10-roadmap/         # 学习路线、面试指南、术语表
```

## 本地开发

```bash
pnpm install
pnpm docs:dev
```

构建：

```bash
pnpm docs:build
```

预览构建产物：

```bash
pnpm docs:preview
```

## 已上线主题

- [大模型从 0 到 1：训练与推理全链路之旅](docs/01-foundation/llm-from-zero/) — 用通俗易懂的方式走完数据 → Tokenizer → Transformer → 预训练 → 后训练 → 推理服务 → 优化加速的完整旅程，穿插真实模型案例（Llama 4 / DeepSeek-V3/R1 / Kimi K2 / Qwen3 / Claude 4）与 2025-2026 前沿动态（内容更新至 2026-07-04）
- [GPU 架构与 CUDA 基础](docs/01-foundation/gpu-cuda/) — 覆盖 GPU 设计哲学、SIMT/Warp/SM、CUDA 编程模型、内存层次与合并访问、NVIDIA 架构演进（Fermi→Blackwell）、Tensor Core/NVLink/HBM、cuBLAS/NCCL/DCGM 软件栈、PyTorch CUDA 调用栈、Nsight 性能分析、生产 GPU 选型与故障排查，含 CPU 可运行 Mini Demo（模拟 warp 调度、coalescing、bank conflict、tiling、occupancy，11 测试）（内容更新至 2026-07-04）
- [Linux 系统与性能调优](docs/01-foundation/linux-systems/) — 覆盖 Linux 内核与用户空间、系统调用、进程/线程/协程、CFS 调度器、nice/RT/CPU 亲和性、虚拟内存/页表/TLB/HugePages/NUMA/swap/page cache、VFS/ext4/xfs/块层/I/O 调度器、网络协议栈/NAPI/RPS/RFS/XDP/RDMA、cgroup v2/namespace/systemd、性能分析工具链（top/vmstat/iostat/mpstat/perf/bpftrace），含 CPU 可运行 Mini Demo（CFS vruntime、LRU page cache、OOM score、noop/deadline/cfq I/O 调度、cgroup CPU/memory 限制，11 测试）（内容更新至 2026-07-04）
- [计算机网络](docs/01-foundation/computer-networks/) — 覆盖 OSI/TCP-IP 分层、分组交换、可靠传输、AIMD/CUBIC 拥塞控制、数据中心 Spine-Leaf/Clos/fat-tree/3D-torus、InfiniBand/RoCEv2/RDMA/RNIC、Kubernetes CNI（bridge/Calico/Cilium/Multus）、kube-proxy（iptables/ipvs/eBPF）、CoreDNS、Service/Ingress/Gateway API、service mesh、L4/L7 负载均衡、DNS/NAT/ARP/VXLAN、网络可观测（ping/traceroute/tcpdump/ss/iperf/nccl-tests/perftest/bcc），含 CPU 可运行 Mini Demo（LPM 路由、滑动窗口、CUBIC-like 拥塞控制、ring/tree all-reduce、DNS TTL + L4 LB，14 测试）（内容更新至 2026-07-04）
- [存储系统](docs/01-foundation/storage-systems/) — 覆盖块/文件/对象三种存储语义与 API、一致性模型、RAID、复制与纠删码、CAP、DAS/NAS/SAN/对象存储/并行文件系统/Lustre/GPFS/WEKA、云端存储服务、Kubernetes PV/PVC/StorageClass/CSI、本地 NVMe checkpoint、异步/增量 checkpoint、对象存储成本治理、缓存与分层（Alluxio/JuiceFS）、PyTorch Distributed Checkpoint 源码、AI 模型服务权重加载，含 CPU 可运行 Mini Demo（块分配、inode 文件系统、对象存储版本/multipart/最终一致性、三副本/XOR 纠删码、热/暖分层缓存、AI checkpoint 保存/加载，12 测试）（内容更新至 2026-07-04）
- [分布式系统基础](docs/01-foundation/distributed-systems/) — 覆盖故障模型、CAP/PACELC、一致性谱系、复制/分区/quorum、共识（Raft/Paxos）、分布式事务/锁/幂等、逻辑时钟/向量时钟，配合 CPU 可运行 Mini Demo（内容更新至 2026-07-04）
- [Kubernetes 详解](docs/02-cloud-native/kubernetes/) — 覆盖声明式 API、控制循环、调度框架 12 扩展点、CRI/CNI/CSI、Device Plugin + GPU 调度（MIG/MPS/拓扑感知）、Gang 调度（Volcano/scheduler-plugins/v1.36 原生 PodGroup）、Deployment 滚动升级、源码分析、Mini Demo（调度框架 + GPU + 滚动 + Gang，56 测试）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [容器运行时详解](docs/02-cloud-native/container-runtime/) — 覆盖 K8s 之下的执行层：从 chroot/LXC/Docker 演进到 OCI 标准化、namespace/cgroup/overlayfs 三件套、Docker→containerd→runc 分层架构、containerd-shim、CRI 与 dockershim 移除、OCI runtime/image spec、源码分析（runc/libcontainer + containerd）、镜像分层与内容寻址、镜像优化（多阶段/distroless/zstd）、镜像供应链安全（cosign 签名/SBOM/trivy/SLSA）、运行时安全（seccomp/capabilities/rootless）、沙箱运行时（gVisor/Kata）、多架构 buildx、惰性拉取（stargz/nydus）、Mini Demo（镜像分层 + overlayfs COW + namespace 隔离 + cgroup throttle/OOM + OCI create/start + 多架构 manifest，40 测试）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [Helm 详解](docs/02-cloud-native/helm/) — 覆盖 K8s 包管理器：裸 YAML 四宗罪、Chart/values/template/Release 四要素、version/appVersion/apiVersion 辨析、Go template + Sprig、values 深合并与分层覆盖、Tiller 移除与客户端渲染、Release Secret 存储、Hook/test/post-renderer、OCI 仓库与 cosign 签名、三方合并 Patch（升级保留人工改动的核心机制）、helm/helm 源码三条主线、GitOps（Argo CD/Flux）部署、External Secrets、AI 推理/Ray/多租户 GPU 配额落地案例、Mini Demo（模板渲染 + Release 生命周期 + 三方合并端到端，55 测试）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [Operator 模式详解](docs/02-cloud-native/operator/) — 覆盖把领域运维知识编码成控制循环：CoreOS 2016 定义、CRD/Controller/Reconcile 四铁律（level-triggered/幂等/不阻塞/乐观）、controller-runtime 全景（Manager/Cache/Client/Workqueue/Leader Election）、finalizer/owner reference/级联 GC/status 子资源/webhook、generation 与 observedGeneration、controller-runtime 源码主干调用链、KubeRay/Training Operator/GPU Operator 三大 AI Operator 对照、Helm+Operator+GitOps 组合、多租户与金丝雀、Mini Demo（纯 Python 从零实现 apiserver/informer/workqueue/reconciler，37 测试，精确复现 reconcile 收敛时间线）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [CNI / CSI 深度详解](docs/02-cloud-native/cni-csi/) — 覆盖 Kubernetes 把网络与存储外包给插件的两根柱子：CNI 接口与插件链（bridge/host-local/IPAM/Flannel/Calico/Cilium/Multus/SR-IOV）、CSI Identity/Controller/Node 三面 gRPC、external-provisioner/attacher/resizer/snapshotter 侧车、NetworkPolicy 数据面（iptables/nftables/eBPF）、VolumeAttachment 一致性、RWO/ROX/RWX、controller/node expand、snapshot/restore、生产排障与 AI 场景选型、Mini Demo（纯 Python 从零实现 CNI/CSI/kubelet，46 测试，精确复现 Pod 网络 + 存储生命周期）、生产实践、最佳实践与面试题（内容更新至 2026-07-05）
- [vLLM 详解](docs/04-llmops/vllm/) — 覆盖 V1 引擎、PagedAttention、Continuous Batching、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [SGLang 详解](docs/04-llmops/sglang/) — 覆盖 LLM Program、RadixAttention、Structured Generation、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [TensorRT-LLM 详解](docs/04-llmops/tensorrt-llm/) — 覆盖 NVIDIA 编译型推理引擎、Builder/Engine/Runtime/Executor、In-flight Batching、Plugin、量化、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [Triton Inference Server 详解](docs/04-llmops/triton/) — 覆盖多框架推理服务、Model Repository、Backend 抽象、Dynamic/Sequence/Ensemble 调度、BLS、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [LLM Gateway 详解](docs/04-llmops/llm-gateway/) — 覆盖访问控制与抽象层、Provider 抽象、统一 OpenAI-compatible API、路由、负载均衡、限流、重试降级、认证、请求/响应转换、成本追踪、可观测、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-02）
- [Ray 详解](docs/03-ai-platform/ray/) — 覆盖 Ray Core tasks/actors/objects、所有权模型、spillback 调度、Plasma 对象存储、引用计数、lineage 重建、Ray Serve/Train/Data/Tune/RLlib/KubeRay、源码与生态分析、Mini Demo（ownership + hybrid 调度 + object store spilling + lineage 重建 + autoscaler，25 测试）、生产实践与面试题（内容更新至 2026-07-03）
- [KServe 详解](docs/03-ai-platform/kserve/) — 覆盖 Kubernetes 模型服务平台：InferenceService / Predictor / Transformer / Explainer / ServingRuntime / ClusterServingRuntime / InferenceGraph、Serverless（Knative）与 RawDeployment、V1/V2/OpenAI-compatible 协议、runtime 自动匹配与模板化、控制面 controller/webhook/ingress/autoscaler 源码链路、Mini Demo（纯 Python 模拟 runtime 选择 / reconcile 渲染 / 网关 canary / HPA 扩缩，20 测试）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [Kubeflow 详解](docs/03-ai-platform/kubeflow/) — 覆盖 Kubernetes 上的 ML 平台：Notebook / Pipelines / Katib / Training Operator / KServe / Central Dashboard / Profiles，KFP v2 DSL → Compiler → IR YAML → Run 链路、Katib Experiment/Trial/Suggestion、Training Operator TFJob/PyTorchJob/MPIJob、多租户与 Istio 认证、源码与调用链、Mini Demo（纯 Python 模拟 Profile → Notebook → Pipeline → Katib → PyTorchJob → KServe，8 测试）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [MLflow 详解](docs/03-ai-platform/mlflow/) — 覆盖开源 ML 生命周期平台：Tracking（Experiment/Run/params/metrics/artifacts/tags）、Projects、Models（MLmodel / flavors / signature / input_example / pyfunc）、Model Registry（Registered Model / Version / Stage / Alias / Tag）、Tracking Server + Backend Store + Artifact Store 架构、REST API 与 Fluent/MlflowClient 调用链、源码分析、Mini Demo（SQLite backend + 本地 artifact 的 sklearn 训练 → log → 注册 → alias → 加载预测）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [KubeRay 详解](docs/03-ai-platform/kuberay/) — 覆盖 Ray 官方 Kubernetes Operator：RayCluster / RayJob / RayService CRD、head/worker 映射、自动扩缩容（Autoscaler sidecar / v2 / idleTimeout / upscalingMode）、GCS Fault Tolerance、声明式升级（NewCluster / Incremental Upgrade）、controller-runtime 架构与三大 Reconciler 调用链、Batch Scheduler 集成（Volcano/YuniKorn/scheduler-plugins）、GPU/TPU 调度、认证与 TLS、Prometheus/Grafana 监控、Mini Demo（FakeClock + FakeApiServer + Informer + WorkQueue + Reconciler 模拟集群创建/扩缩容/RayJob 生命周期）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [Airflow 详解](docs/03-ai-platform/airflow/) — 覆盖工作流编排平台：DAG / Operator / Task / TaskInstance / DAG Run / Executor（Sequential/Local/Celery/Kubernetes/Dask，Airflow 2.10+ 多 Executor）/ Metadata Database / Triggerer / DAG Processor / XCom / Deferrable Operator / Dataset/Asset 调度、Airflow 3 Execution API + JWT 演进、源码分析（models/jobs/executors/providers）、Mini Demo（纯 Python 模拟 DAG 解析/Scheduler/Executor/XCom/Triggerer，11 测试）、生产实践、最佳实践与面试题（内容更新至 2026-07-04）
- [Agent Runtime 详解](docs/05-agent/agent-runtime/) — 覆盖 ReAct 循环、工具注册与 function calling、记忆、状态机、护栏、可观测、恢复、与 LLM Gateway 集成、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Memory 详解](docs/05-agent/memory/) — 覆盖 Agent 记忆系统、工作记忆、短期记忆、长期语义记忆、episodic 记忆、向量检索、存储后端、与 Agent Runtime 集成、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Multi-Agent 详解](docs/05-agent/multi-agent/) — 覆盖多 Agent 协作、角色定义、消息通信、协调调度、共享黑板、团队可观测、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Reflection 详解](docs/05-agent/reflection/) — 覆盖 Agent 自我反思与纠错、生成—批判—评估—修订闭环、Generator/Critic/Evaluator/Revision Controller/Workspace/Observer、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [MCP 详解](docs/05-agent/mcp/) — 覆盖 Model Context Protocol、Host/Client/Server 角色、Tools/Resources/Prompts、JSON-RPC 协议流程、Capability negotiation、Transport（stdio/SSE/HTTP）、官方 SDK 源码、Mini Demo、企业生产实践与面试题（内容更新至 2026-07-03）
- [Planning 详解](docs/05-agent/planning/) — 覆盖 Agent 规划系统、任务分解范式、计划表示（列表/DAG/树/状态图）、Plan-Execute-Observe-Replan 循环、动态重规划、与 Runtime/Memory/Reflection/Multi-Agent/MCP 集成、源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Tool Use 详解](docs/05-agent/tool-use/) — 覆盖 Agent 工具调用、JSON Schema 工具定义、Tool Choice、并行调用、解析/校验/执行/结果格式化、OpenAI/Anthropic/Google/LangGraph/OpenAI Agents SDK/AutoGen/MCP 源码对比、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Agent OS 详解](docs/05-agent/agent-os/) — 覆盖 Agent 运行时操作系统、进程/生命周期、调度、沙箱、Workspace、Capability/权限、Registry、MCP Host 与 A2A IPC、AIOS/Agent libOS/Quine 等源码、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [RAG 详解](docs/06-rag/) — 覆盖检索增强生成、Chunking、Embedding、Vector Store、Dense/Sparse/Hybrid 检索、RRF、Reranking、GraphRAG、评估体系、源码与生态分析、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [AI SRE 详解](docs/07-ai-sre/) — 覆盖 AI 系统可观测性、OpenTelemetry GenAI 语义约定、SLI/SLO/Error Budget、Burn Rate 告警、AIOps、事故响应与复盘、源码与生态分析、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Benchmark + Evaluation 详解](docs/07-ai-sre/benchmark-evaluation/) — 覆盖 Agent / LLM / RAG 的可复现评测框架：评测维度（正确性、工具使用、延迟、成本、鲁棒性）、trace-based eval、benchmark 数据集、LLM-as-judge 与规则评估器、离线/在线评测、CI 评估门与生产回归检测，含 CPU 可运行 Mini Demo（确定性 ReAct Agent + tool use + tracer + evaluators，15 测试）（内容更新至 2026-07-04）
- [安全详解](docs/08-security/) — 覆盖 AI 系统安全、IAM/AuthN/AuthZ、Secrets 管理、Zero Trust、Guardrails、合规与隐私治理、源码与生态分析、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [OpenAI 案例研究详解](docs/09-case-study/openai/) — 覆盖 OpenAI 训练与推理基础设施、Azure AI 超级计算机、H100/H200/InfiniBand、连续批处理与 KV Cache 管理、推测解码与预测输出、流式生成、RLHF 与对齐、Red Teaming/Preparedness Framework/System Cards、Triton/Whisper/CLIP、源码与生态分析、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Anthropic 案例研究详解](docs/09-case-study/anthropic/) — 覆盖 Anthropic 异构算力（AWS Trainium Project Rainier >100 万芯片/5GW、SpaceXAI Colossus 22 万 GPU）、Constitutional AI/RLAIF 两阶段对齐、机制可解释性（transformer-circuits/dictionary learning/Circuit Tracing）、prompt caching（prefix hash + 20-block lookback、5m/1h TTL、pre-warm、workspace 隔离）、extended thinking/computer use/Batch API、RSP/ASL 安全治理、源码与可解释性生态分析、Mini Demo、生产实践与面试题（内容更新至 2026-07-03）
- [Meta 案例研究详解](docs/09-case-study/meta/) — 覆盖 Meta 基础设施演进（LAMP/Twine/Tectonic → GPU 推荐系统 → 24k/129k H100 GenAI 集群 → Prometheus 1GW/Hyperion 5GW）、开放权重 + OCP 硬件协同设计（Grand Teton/Catalina GB200/MTIA 300–500）、RoCE 与 InfiniBand 双网络织物 + fat-tree 拓扑、同步训练可靠性工程（SDC 治理 Fleetscanner/Ripple/Hardware Sentinel、~50x 中断下降、>95% 有效训练时间）、Tectonic/Hammerspace 存储、PyTorch/FSDP/torch.compile/Triton/Llama Stack/vLLM 开源生态、Llama 3/4 训练与 MoE/iRoPE 推理、Mini Demo（训练集群可靠性 + checkpoint/SDC 模拟器）、生产实践与面试题（内容更新至 2026-07-03）
- [Google 案例研究详解](docs/09-case-study/google/) — 覆盖 TPU 十年自研硅演进（v1→Ironwood，MXU 权重驻留脉动阵列/SparseCore 5×–7×/3D-torus/OCS 可重配拓扑）、NSDI'24 大规模可靠性（healthd + preflight end-to-end check + intent-driven checker、reconfigure 迁移 vs reroute 容错 ICI 路由双路径、99.98% 可用率、每日 0.08% 机器/0.005% ICI 缆/0.04% OCS 故障率、reroute 0.5%–8.6% 步时税）、Falcon 硬件传输（不依赖 PFC、8× 优于 RoCE）、Multislice 跨 Pod 训练（58.9% MFU）、GSPMD/Pathways 编译器自动并行与单控制器、Borg 调度协同、JetStream/tpu-inference 原生推理 + DFlash 投机解码（~3×）、Gemma 3、AI Principles/Frontier Safety Framework、可持续性（PUE 1.09/24/7 CFE）、开源软件栈（JAX/XLA/MaxText）+ 闭源硬件、Mini Demo（3D-torus 延迟优势 + NSDI 双路径恢复模拟器，38 测试）、生产实践与面试题（内容更新至 2026-07-03）

## 内容更新说明

- 本手册优先引用官方文档、论文、源码与生产实践，避免依赖过时第三方内容。
- vLLM 主题已基于 2026 年中主分支（默认 V1 引擎）进行更新。
- SGLang 主题已基于 2026 年 7 月 v0.5.14 进行更新。

## 贡献

欢迎提交 Issue 和 PR。请遵循统一的章节结构与文档风格。

## License

[CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
