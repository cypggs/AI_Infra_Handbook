# 11. 延伸阅读

本章汇总 Meta AI 基础设施相关的权威来源、官方博客、论文、OCP/Llama Stack 资源，以及与本手册其他主题的交叉引用。

## 官方博客（一手来源）

- [Building Meta's GenAI Infrastructure](https://engineering.fb.com/2024/03/12/data-infrastructure/building-metas-genai-infrastructure/)（2024-03-12）— 两个 24k H100 集群（RoCE + InfiniBand）、Grand Teton、Tectonic/Hammerspace 存储、AllGather 调优、checkpoint 的权威描述。
- [Meta's Infrastructure Evolution and the Advent of AI](https://engineering.fb.com/2025/09/29/data-infrastructure/meta-infrastructure-evolution-ai/)（2025-09-29）— 从 LAMP/Twine/Tectonic 到 GPU 推荐系统再到 GenAI 的完整演进；Prometheus（1GW）/ Hyperion（5GW）；Catalina/GB200；MTIA；Twine + MAST 长距离训练。
- [How Meta keeps its AI hardware reliable](https://engineering.fb.com/2025/07/22/data-infrastructure/how-meta-keeps-its-ai-hardware-reliable/)（2025-07-22）— 三类硬件故障（static/transient/silent）、SDC ~1/1000 设备、Fleetscanner/Ripple/Hardware Sentinel 三层检测、训练 SDC（NaN 传播/梯度方差污染）、factory-to-fleet。
- [Zoomer: Powering AI Performance at Meta's Scale Through Intelligent Debugging and Optimization](https://engineering.fb.com/2025/11/21/data-infrastructure/zoomer-powering-ai-performance-meta-intelligent-debugging-optimization/)（2025-11-21）— AI 性能调试平台：straggler 检测、关键路径分析、一键 QPS 优化；100k+ GPU 工作负载；广告训练时间 -75%。
- [DrP: Meta's Root Cause Analysis Platform at Scale](https://engineering.fb.com/2025/12/19/data-infrastructure/drp-metas-root-cause-analysis-platform-at-scale/)（2025-12-19）— 自动化 RCA：300+ 团队、每天 5 万次自动分析、MTTR 降 20–80%。
- [Meta's AI Storage Blueprint at Scale](https://engineering.fb.com/2026/07/01/data-center-engineering/metas-ai-storage-blueprint-at-scale/)（2026-07-01）— 存储栈 BLOB 化重构、Owl 缓存 ~80% 命中、L1/L2/L3 分层缓存。
- [MetaRoCE: A New RDMA Transport Built for AI-Scale Ethernet](https://engineering.fb.com/2026/08/24/networking-traffic/metaroce-rdma-transport-ai-ethernet/)（2026-08-24）— 自研 RDMA 传输层：有损以太网假设、端点喷洒、256-bit 选择确认、1% 丢包 ~86% 吞吐。
- [MTIA 300: Meta's First Training Chip with Built-in NICs and Communication-Offloading Engines](https://engineering.fb.com/2026/08/24/networking-traffic/mtia-300-meta-training-chip-built-in-nics/)（2026-08-24）— 12×800G 内置 NIC、16 message engine、2.8 TB/s 归约、通信干扰 <0.5%。
- [OCP Summit 2026: Powering AI with Open Innovations in Scale-Up, Scale-Out, and Scale-Across Networks](https://engineering.fb.com/2026/10/12/open-source/ocp-summit-2026-powering-ai-with-open-innovations-in-scale-up-scale-out-and-scale-across-networks/)（2026-10-12）— IcePack/IceCube/FPF/OSPA/Tahan/BAG/ESUN 全套开放网络发布。
- [Four MTIA Chips in Two Years](https://ai.meta.com/blog/meta-mtia-scale-ai-chips-for-billions/) — MTIA 300/400/450/500 详细规格、High velocity/Inference First/PyTorch Native 三原则、HCCL、Rust 驱动/固件、agentic kernel 生成（TritorX/KernelEvolve）。
- [Introducing Meta Llama 3](https://ai.meta.com/blog/meta-llama-3/) — Llama 3 架构（GQA、128K 词表、15T token）、>400 TFLOPS/GPU、>95% 有效训练时间、SDC 检测、后训练管线。
- [The Llama 4 herd](https://ai.meta.com/blog/llama-4-multimodal-intelligence/) — Llama 4 Scout/Maverick/Behemoth、MoE、early fusion、iRoPE、FP8 + 32k GPU、390 TFLOPS/GPU、codistillation、异步 online RL。
- [Muse Spark Is Now an Open-Weights Model（PyTorch 官方博客）](https://pytorch.org/blog/muse-spark-open/)（2026-10-15）— Muse Spark Open：816B/42B MoE、Helion kernel 1.03–3.95×、SGLang/vLLM 双引擎、两台 Mac Studio 可运行、TorchTitan 微调支持。
- [Engineering at Meta](https://engineering.fb.com/) — 持续关注硬件、网络、存储、可靠性新发布。

## 行业报道（二手来源）

- [Meta expands Louisiana data center to 5 gigawatts](https://www.reuters.com/business/meta-expands-louisiana-data-center-5-gigawatts-compute-capacity-2026-07-13/)（Reuters，2026-07-13）— Hyperion 2GW → 5GW 扩建。
- [Meta Locks In Three Nuclear Deals For Ohio AI Supercluster](https://www.forbes.com/sites/sofiachierchio/2026/01/09/meta-locks-in-three-nuclear-deals-for-ohio-ai-supercluster/)（Forbes，2026-01-09）— Vistra/Oklo/TerraPower 三笔核电协议，2035 年合计 ~6.6GW。
- [Meta abandons open-source Llama for proprietary Muse Spark](https://thenewstack.io/meta-abandons-llama-spark/)（The New Stack，2026-04）— MSL 与 Muse 转型的背景分析。
- [Meta opens a weaker AI model while keeping the frontier closed](https://thenextweb.com/news/meta-muse-spark-open-weights-eu)（The Next Web，2026-10）— Muse Spark Open 发布与 Alexandr Wang "通常不会开源最强模型" 的表态。

## 论文与技术报告

- **The Llama 3 Herd of Models** — [arXiv:2407.21783](https://arxiv.org/abs/2407.21783) — Llama 3 全栈技术报告（含基础设施与可靠性章节）。
- **The Llama 4 Herd: The Beginning of a New Era of Natively Multimodal AI Innovation** — Llama 4 技术细节。
- **MTIA（ISCA'23 / ISCA'25 / ISCA'26）** — MTIA 100 / MTIA 200（原名 MTIA 1 / MTIA 2i）/ MTIA 300（内置 NIC 与通信卸载）体系结构论文。
- **HCCL（SC'26）** — MTIA 300 上把集合通信编译为自主 work-queue 子图的通信库论文。
- **DrP: Meta's Efficient Investigations Platform at Scale** — [arXiv:2512.04250](https://arxiv.org/abs/2512.04250) — 自动化根因分析平台（300+ 团队、5 万次分析/天）。
- **Silent Data Corruptions at Scale** — Meta 2020 年 SDC 开创性论文。
- **Detecting Silent Errors in the Wild** — Fleetscanner / Ripple 检测框架。
- **Hardware Sentinel** — test-agnostic、内核态 SDC 检测（比 testing-based +41%）。
- **Fully Sharded Data Parallel（FSDP）** — [arXiv:2304.11277](https://arxiv.org/abs/2304.11277)（FSDP 论文）。
- **PagedAttention / vLLM** — [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)（SOSP 2023）。
- **Llama Guard** — [arXiv:2312.06674](https://arxiv.org/abs/2312.06674) — 输入/输出安全分类器。

## 开源项目

- [PyTorch](https://github.com/pytorch/pytorch) — Meta 主要贡献的训练/推理框架。
- [FSDP / FSDP2](https://github.com/pytorch/pytorch/tree/main/torch/distributed/fsdp) — 分片数据并行。
- [Triton](https://github.com/triton-lang/triton) — GPU kernel 语言与编译器。
- [Helion](https://pytorch.org/blog/helion/) — PyTorch 原生 kernel DSL（2026-04 进入 PyTorch Foundation）。
- [TorchTitan](https://github.com/pytorch/torchtitan) — PyTorch 原生大模型训练平台（含 TitanRL；2026-10 官方支持 Muse Spark Open）。
- [torchtune](https://github.com/pytorch/torchtune) — PyTorch 原生微调库。
- [ExecuTorch](https://github.com/pytorch/executorch) — 移动/边缘推理。
- [vLLM](https://github.com/vllm-project/vllm) — 服务端推理（PagedAttention）。
- [SGLang](https://github.com/sgl-project/sglang) — Muse Spark Open 双官方引擎之一（Helion megakernel）。
- [Llama Stack](https://github.com/meta-llama/llama-stack) — 9 类标准化服务 API。
- [Llama 模型](https://github.com/meta-llama/llama-models) + [Hugging Face](https://huggingface.co/meta-llama) — 开放权重。
- [Llama Guard](https://github.com/meta-llama/PurpleLlama) — Purple Llama 安全工具集（Llama Guard / Prompt Guard / CyberSecEval）。

## 开放计算（OCP）

- [Open Compute Project](https://www.opencompute.org/) — Meta 是创始成员，贡献约 187 项（~25%）硬件规范。
- **Grand Teton** — OCP 开放 GPU 平台规范。
- **Catalina** — GB200 Blackwell 开放机柜设计。
- **Open Rack** — 标准化机柜电源与机械结构。
- **MetaRoCE / FPF / IcePack / IceCube / Tahan / BAG / OSPA / ESUN** — OCP Summit 2026 发布的开放网络全套规范（见 2026-10-12 官方博客）。

## Llama Stack 与服务生态

- [Llama Stack 文档](https://llama-stack.readthedocs.io/) — Inference / Safety / Agentic / Memory / Eval / Telemetry / Post-training / Toolchain / RAG 九类 API。
- [llama.com](https://www.llama.com/) — 模型下载与生态入口（2026 年起 Meta 开发者模型中心转向 dev.meta.ai 的 Muse 系列）。

## 演讲与会议

- **@Scale** — Meta 的基础设施大会（"Scaling Llama 4 Training to 100K" 等主题）。
- **ISCA** — MTIA 体系结构论文发表。
- **MLCommons** — 安全风险分类法（Llama Guard 基于此）。

## 本手册交叉引用

- [vLLM 详解](/04-llmops/vllm/) — PagedAttention、continuous batching；MTIA 提供 vLLM plugin backend，Llama 推理事实标准。
- [LLM Gateway 详解](/04-llmops/llm-gateway/) — Llama Stack Inference API 提供跨云/跨硬件统一入口。
- [Agent Runtime 详解](/05-agent/agent-runtime/) — Llama Stack Agent API 把 tool-calling/memory/shielding 标准化。
- [RAG 详解](/06-rag/) — Llama Stack RAG API。
- [AI SRE 详解](/07-ai-sre/) — 同步训练故障闭环、SDC 治理、有效训练时间 SLO、~50x 中断下降。
- [安全详解](/08-security/) — Llama Guard 2 / Prompt Guard / CyberSecEval 2 / Code Shield / GOAT 红队，开放权重安全治理。
- [OpenAI 案例研究](/09-case-study/openai/) — 对照"闭源规模"与"开放权重 + 硬件协同设计"。
- [Anthropic 案例研究](/09-case-study/anthropic/) — 对照"闭源对齐"与"开放发布 + 自研硅"。
- [Google 案例研究](/09-case-study/google/) — 对照"开放软件栈 + 闭源 TPU 硅 + JAX/GSPMD"与"开放权重 + OCP 硬件 + PyTorch"；NSDI'24 双路径恢复 vs Meta 的 SDC 治理。

## 学习路径建议

1. **入门**：读《Building Meta's GenAI Infrastructure》（2024-03-12）建立集群全貌；理解同步训练为何改变可靠性模型（[第 1 章](01-background)）。
2. **架构**：读《Meta's Infrastructure Evolution》（2025-09-29）理解演进脉络与 Prometheus/Hyperion 路线（[第 3 章](03-architecture)）。
3. **可靠性**：读《How Meta keeps its AI hardware reliable》（2025-07-22）深入 SDC 治理；跑通 [Mini Demo](07-mini-demo) 量化 checkpoint/SDC trade-off；读 Zoomer（2025-11）与 DrP（2025-12）理解平台化性能工程与 AI4Ops。
4. **网络**：读 MetaRoCE（2026-08-24）与 OCP Summit 2026（2026-10-12）两篇，理解从"双织物验证"到"自定义传输层 + 三层网络框架"的跃迁。
5. **自研硅**：读《Four MTIA Chips》与 MTIA 300 专文（ISCA'26）理解协同设计、通信卸载与 PyTorch Native 栈（[第 5 章](05-core-modules)、[第 6 章](06-source-analysis)）。
6. **模型**：读 Llama 3 / Llama 4 博客与论文理解训练/推理工程（[第 4 章](04-training-and-inference)）；读 PyTorch 博客《Muse Spark Is Now an Open-Weights Model》（2026-10-15）理解 Muse 时代的开放 kernel 与双引擎推理。
7. **生态**：浏览 Llama Stack 文档与 OCP 规范，理解开放如何成为规模杠杆（[第 8 章](08-production-practice)、[第 9 章](09-best-practices)）。

## 一句话收尾

Meta 的公开资料是研究"如何造一个 AI 数据中心"最完整的样本——它不仅公开模型权重，还公开硬件设计、软件栈、可靠性工程与规模路线。持续关注 Engineering at Meta、ai.meta.com/blog、OCP 与 Llama Stack 的发布，是跟上 AI 基础设施前沿的必要投入。
