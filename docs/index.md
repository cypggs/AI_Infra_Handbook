---
layout: home

hero:
  name: "AI Infra Handbook"
  text: "AI 基础设施工程师手册"
  tagline: 从 Kubernetes 到 LLMOps，系统构建生产级 AI 基础设施知识体系
  actions:
    - theme: brand
      text: 开始阅读
      link: /guide
    - theme: alt
      text: 学习路线
      link: /10-roadmap/learning-path
    - theme: alt
      text: 大模型从 0 到 1
      link: /01-foundation/llm-from-zero/
    - theme: alt
      text: GPU/CUDA 详解
      link: /01-foundation/gpu-cuda/
    - theme: alt
      text: Linux 系统调优
      link: /01-foundation/linux-systems/
    - theme: alt
      text: 计算机网络
      link: /01-foundation/computer-networks/
    - theme: alt
      text: 存储系统
      link: /01-foundation/storage-systems/
    - theme: alt
      text: 分布式系统基础
      link: /01-foundation/distributed-systems/
    - theme: alt
      text: vLLM 详解
      link: /04-llmops/vllm/
    - theme: alt
      text: SGLang 详解
      link: /04-llmops/sglang/
    - theme: alt
      text: TensorRT-LLM 详解
      link: /04-llmops/tensorrt-llm/
    - theme: alt
      text: Triton 详解
      link: /04-llmops/triton/
    - theme: alt
      text: LLM Gateway 详解
      link: /04-llmops/llm-gateway/
    - theme: alt
      text: Kubernetes 详解
      link: /02-cloud-native/kubernetes/
    - theme: alt
      text: Helm 详解
      link: /02-cloud-native/helm/
    - theme: alt
      text: Operator 模式详解
      link: /02-cloud-native/operator/
    - theme: alt
      text: CNI / CSI 深度详解
      link: /02-cloud-native/cni-csi/
    - theme: alt
      text: Ray 详解
      link: /03-ai-platform/ray/
    - theme: alt
      text: KServe 详解
      link: /03-ai-platform/kserve/
    - theme: alt
      text: Kubeflow 详解
      link: /03-ai-platform/kubeflow/
    - theme: alt
      text: MLflow 详解
      link: /03-ai-platform/mlflow/
    - theme: alt
      text: KubeRay 详解
      link: /03-ai-platform/kuberay/
    - theme: alt
      text: Airflow 详解
      link: /03-ai-platform/airflow/
    - theme: alt
      text: Agent Runtime 详解
      link: /05-agent/agent-runtime/
    - theme: alt
      text: Memory 详解
      link: /05-agent/memory/
    - theme: alt
      text: Multi-Agent 详解
      link: /05-agent/multi-agent/
    - theme: alt
      text: Reflection 详解
      link: /05-agent/reflection/
    - theme: alt
      text: MCP 详解
      link: /05-agent/mcp/
    - theme: alt
      text: Planning 详解
      link: /05-agent/planning/
    - theme: alt
      text: Tool Use 详解
      link: /05-agent/tool-use/
    - theme: alt
      text: Agent OS 详解
      link: /05-agent/agent-os/
    - theme: alt
      text: RAG 详解
      link: /06-rag/
    - theme: alt
      text: AI SRE 详解
      link: /07-ai-sre/
    - theme: alt
      text: Benchmark + Evaluation
      link: /07-ai-sre/benchmark-evaluation/
    - theme: alt
      text: 安全详解
      link: /08-security/
    - theme: alt
      text: OpenAI 案例
      link: /09-case-study/openai/
    - theme: alt
      text: Anthropic 案例
      link: /09-case-study/anthropic/
    - theme: alt
      text: Meta 案例
      link: /09-case-study/meta/
    - theme: alt
      text: Google 案例
      link: /09-case-study/google/

features:
  - icon: 📚
    title: 系统化
    details: 覆盖基础、云原生、AI 平台、LLMOps、Agent、RAG、AI SRE、安全、案例、路线十大模块。
  - icon: 🔧
    title: 工程化
    details: 每个主题都包含源码分析、Mini Demo、生产实践、最佳实践与面试题，强调可落地。
  - icon: 🌐
    title: 开源协作
    details: 采用 CC-BY-SA-4.0 协议，欢迎提交 PR、Issue 与改进建议，长期维护。
  - icon: 🧠
    title: 面向实践
    details: 不翻译文档，不堆砌 API，而是讲透设计思想、工程实现与真实踩坑经验。
---

## 一句话理解

> **AI Infra Handbook 不是教程合集，而是一本面向 AI 基础设施工程师的长期维护的工程手册。**

它帮助一名已经具备 Kubernetes / Linux 基础的工程师，成长为能够设计和构建 AI 基础设施的平台工程师、LLMOps Engineer 或 AI SRE。

## 当前进度

- [x] 项目骨架与 VitePress 初始化
- [x] 大模型从 0 到 1 主题（数据 → Tokenizer → Transformer → 预训练 → 后训练 → 推理服务 → 优化加速）
- [x] GPU/CUDA 主题（硬件架构、CUDA 编程模型、NVIDIA 软件栈、生产实践）
- [x] Linux 系统与性能调优主题（Kernel/User Space、进程调度、内存管理、I/O、网络、cgroup/namespace、性能分析，含 CPU 可运行 Mini Demo）
- [x] 计算机网络主题（OSI/TCP-IP、分组交换、可靠传输、拥塞控制、数据中心拓扑、RDMA/RoCE/InfiniBand、K8s CNI/Service/DNS/LB，含 CPU 可运行 Mini Demo）
- [x] 存储系统主题（块/文件/对象、一致性、复制与纠删码、DAS/NAS/SAN/并行文件系统、K8s CSI、PyTorch DCP，含 CPU 可运行 Mini Demo）
- [x] 分布式系统基础主题（故障模型、CAP/PACELC、一致性谱系、复制/分区/quorum/共识/Raft、分布式事务/锁/幂等、逻辑时钟/向量时钟，含 CPU 可运行 Mini Demo）
- [x] Kubernetes 主题（容器编排底座、调度框架、GPU/Gang 调度）
- [x] 容器运行时主题（K8s 之下的执行层：namespace/cgroup/overlayfs、OCI、containerd/runc、镜像供应链安全、沙箱运行时、惰性拉取）
- [x] Helm 主题（K8s 包管理器：Chart/values/template/Release、Tiller 移除与客户端渲染、三方合并 Patch、OCI、GitOps）
- [x] Operator 主题（CRD + 控制循环、Reconcile 四铁律、controller-runtime 架构、finalizer/owner/status/webhook、KubeRay/Training Operator/GPU Operator 源码对照、纯 Python Mini Demo）
- [x] CNI / CSI 深度主题（K8s 网络与存储插件接口：CNI ADD/DEL、CSI Controller/Node、NetworkPolicy、VolumeAttachment、RWO/ROX/RWX、生产排障、纯 Python Mini Demo）
- [x] vLLM 主题（LLM 推理引擎）
- [x] SGLang 主题（LLM Program / RadixAttention / 结构化生成）
- [x] TensorRT-LLM 主题（NVIDIA 编译型 LLM 推理引擎）
- [x] Triton Inference Server 主题（多框架推理服务软件）
- [x] LLM Gateway 主题（访问控制与抽象层）
- [x] Ray 主题（统一分布式 AI 计算框架）
- [x] KServe 主题（Kubernetes 模型服务平台：InferenceService / ServingRuntime / InferenceGraph）
- [x] Kubeflow 主题（Kubernetes 上的 ML 平台：Notebook / Pipelines / Katib / Training Operator / KServe / Central Dashboard）
- [x] MLflow 主题（开源 ML 生命周期平台：Tracking / Models / Model Registry / 生产部署）
- [x] KubeRay 主题（Ray 官方 Kubernetes Operator：RayCluster / RayJob / RayService / 自动扩缩容 / GCS FT）
- [x] Airflow 主题（工作流编排平台：DAG / Operator / Scheduler / Executor / Metadata DB / Triggerer / XCom / Deferrable Operator）
- [x] Agent Runtime 主题（AI Agent 执行容器）
- [x] Memory 主题（AI Agent 记忆系统）
- [x] Multi-Agent 主题（多 Agent 协作系统）
- [x] Reflection 主题（Agent 自我反思与纠错系统）
- [x] MCP 主题（模型上下文协议）
- [x] Planning 主题（Agent 规划系统）
- [x] Tool Use 主题（Agent 工具调用）
- [x] Agent OS 主题（Agent 运行时操作系统）
- [x] RAG 主题（检索增强生成）
- [x] AI SRE 主题（可观测性、可靠性、AIOps）
- [x] Benchmark + Evaluation 主题（Agent / LLM / RAG 可复现评测框架：trace-based eval、benchmark 数据集、CI 评估门、生产回归检测）
- [x] 安全主题（IAM、Secrets、Zero Trust、合规）
- [x] OpenAI 案例研究（训练/推理基础设施、安全与对齐）
- [x] Anthropic 案例研究（宪法对齐、可解释性、异构算力、prompt caching）
- [x] Meta 案例研究（开放权重、硬件协同设计、双网络织物、SDC 治理、MTIA 自研硅）
- [x] Google 案例研究（TPU 自研硅、3D-torus/OCS、NSDI'24 双路径恢复、GSPMD/Pathways、开放软件栈）
- [ ] 更多主题持续建设中……

## 如何阅读

1. 如果你是新手，建议从 [学习路线](/10-roadmap/learning-path) 开始。
2. 如果你想快速了解一个主题，先看 [阅读指南](/guide)。
3. 如果你关注当前最热门的 LLM 推理引擎，直接阅读 [Kubernetes 详解](/02-cloud-native/kubernetes/)、[Helm 详解](/02-cloud-native/helm/)、[Operator 模式详解](/02-cloud-native/operator/)、[容器运行时详解](/02-cloud-native/container-runtime/)、[vLLM 详解](/04-llmops/vllm/)、[SGLang 详解](/04-llmops/sglang/)、[TensorRT-LLM 详解](/04-llmops/tensorrt-llm/)、[Triton 详解](/04-llmops/triton/)、[LLM Gateway 详解](/04-llmops/llm-gateway/)、[Ray 详解](/03-ai-platform/ray/)、[KServe 详解](/03-ai-platform/kserve/)、[Kubeflow 详解](/03-ai-platform/kubeflow/)、[MLflow 详解](/03-ai-platform/mlflow/)、[KubeRay 详解](/03-ai-platform/kuberay/)、[Airflow 详解](/03-ai-platform/airflow/)、[Agent Runtime 详解](/05-agent/agent-runtime/)、[Memory 详解](/05-agent/memory/)、[Multi-Agent 详解](/05-agent/multi-agent/)、[Reflection 详解](/05-agent/reflection/)、[MCP 详解](/05-agent/mcp/)、[Planning 详解](/05-agent/planning/)、[Tool Use 详解](/05-agent/tool-use/)、[Agent OS 详解](/05-agent/agent-os/)、[RAG 详解](/06-rag/)、[AI SRE 详解](/07-ai-sre/)、[安全详解](/08-security/)、[Linux 系统与性能调优](/01-foundation/linux-systems/) 或 [OpenAI 案例研究](/09-case-study/openai/)、[Anthropic 案例研究](/09-case-study/anthropic/)、[Meta 案例研究](/09-case-study/meta/)、[Google 案例研究](/09-case-study/google/)。

## 贡献

欢迎通过 GitHub 提交 Issue 和 PR。所有内容采用 CC-BY-SA-4.0 协议授权。

## License

[CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
