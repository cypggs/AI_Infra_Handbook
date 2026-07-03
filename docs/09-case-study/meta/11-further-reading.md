# 11. 延伸阅读

本章汇总 Meta AI 基础设施相关的权威来源、官方博客、论文、OCP/Llama Stack 资源，以及与本手册其他主题的交叉引用。

## 官方博客（一手来源）

- [Building Meta's GenAI Infrastructure](https://engineering.fb.com/2024/03/12/data-infrastructure/building-metas-genai-infrastructure/)（2024-03-12）— 两个 24k H100 集群（RoCE + InfiniBand）、Grand Teton、Tectonic/Hammerspace 存储、AllGather 调优、checkpoint 的权威描述。
- [Meta's Infrastructure Evolution and the Advent of AI](https://engineering.fb.com/2025/09/29/data-infrastructure/meta-infrastructure-evolution-ai/)（2025-09-29）— 从 LAMP/Twine/Tectonic 到 GPU 推荐系统再到 GenAI 的完整演进；Prometheus（1GW）/ Hyperion（5GW）；Catalina/GB200；MTIA；Twine + MAST 长距离训练。
- [How Meta keeps its AI hardware reliable](https://engineering.fb.com/2025/07/22/data-infrastructure/how-meta-keeps-its-ai-hardware-reliable/)（2025-07-22）— 三类硬件故障（static/transient/silent）、SDC ~1/1000 设备、Fleetscanner/Ripple/Hardware Sentinel 三层检测、训练 SDC（NaN 传播/梯度方差污染）、factory-to-fleet。
- [Four MTIA Chips in Two Years](https://ai.meta.com/blog/meta-mtia-scale-ai-chips-for-billions/) — MTIA 300/400/450/500 详细规格、High velocity/Inference First/PyTorch Native 三原则、HCCL、Rust 驱动/固件、agentic kernel 生成（TritorX/KernelEvolve）。
- [Introducing Meta Llama 3](https://ai.meta.com/blog/meta-llama-3/) — Llama 3 架构（GQA、128K 词表、15T token）、>400 TFLOPS/GPU、>95% 有效训练时间、SDC 检测、后训练管线。
- [The Llama 4 herd](https://ai.meta.com/blog/llama-4-multimodal-intelligence/) — Llama 4 Scout/Maverick/Behemoth、MoE、early fusion、iRoPE、FP8 + 32k GPU、390 TFLOPS/GPU、codistillation、异步 online RL。
- [Engineering at Meta](https://engineering.fb.com/) — 持续关注硬件、网络、存储、可靠性新发布。

## 论文与技术报告

- **The Llama 3 Herd of Models** — [arXiv:2407.21783](https://arxiv.org/abs/2407.21783) — Llama 3 全栈技术报告（含基础设施与可靠性章节）。
- **The Llama 4 Herd: The Beginning of a New Era of Natively Multimodal AI Innovation** — Llama 4 技术细节。
- **MTIA（ISCA'23 / ISCA'25）** — MTIA 100 / MTIA 200（原名 MTIA 1 / MTIA 2i）体系结构论文。
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
- [torchtune](https://github.com/pytorch/torchtune) — PyTorch 原生微调库。
- [ExecuTorch](https://github.com/pytorch/executorch) — 移动/边缘推理。
- [vLLM](https://github.com/vllm-project/vllm) — 服务端推理（PagedAttention）。
- [Llama Stack](https://github.com/meta-llama/llama-stack) — 9 类标准化服务 API。
- [Llama 模型](https://github.com/meta-llama/llama-models) + [Hugging Face](https://huggingface.co/meta-llama) — 开放权重。
- [Llama Guard](https://github.com/meta-llama/PurpleLlama) — Purple Llama 安全工具集（Llama Guard / Prompt Guard / CyberSecEval）。

## 开放计算（OCP）

- [Open Compute Project](https://www.opencompute.org/) — Meta 是创始成员，贡献约 187 项（~25%）硬件规范。
- **Grand Teton** — OCP 开放 GPU 平台规范。
- **Catalina** — GB200 Blackwell 开放机柜设计。
- **Open Rack** — 标准化机柜电源与机械结构。

## Llama Stack 与服务生态

- [Llama Stack 文档](https://llama-stack.readthedocs.io/) — Inference / Safety / Agentic / Memory / Eval / Telemetry / Post-training / Toolchain / RAG 九类 API。
- [llama.com](https://www.llama.com/) — 模型下载与生态入口。

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

## 学习路径建议

1. **入门**：读《Building Meta's GenAI Infrastructure》（2024-03-12）建立集群全貌；理解同步训练为何改变可靠性模型（[第 1 章](01-background)）。
2. **架构**：读《Meta's Infrastructure Evolution》（2025-09-29）理解演进脉络与 Prometheus/Hyperion 路线（[第 3 章](03-architecture)）。
3. **可靠性**：读《How Meta keeps its AI hardware reliable》（2025-07-22）深入 SDC 治理；跑通 [Mini Demo](07-mini-demo) 量化 checkpoint/SDC trade-off。
4. **自研硅**：读《Four MTIA Chips》理解协同设计与 PyTorch Native 栈（[第 5 章](05-core-modules)、[第 6 章](06-source-analysis)）。
5. **模型**：读 Llama 3 / Llama 4 博客与论文理解训练/推理工程（[第 4 章](04-training-and-inference)）。
6. **生态**：浏览 Llama Stack 文档与 OCP 规范，理解开放如何成为规模杠杆（[第 8 章](08-production-practice)、[第 9 章](09-best-practices)）。

## 一句话收尾

Meta 的公开资料是研究"如何造一个 AI 数据中心"最完整的样本——它不仅公开模型权重，还公开硬件设计、软件栈、可靠性工程与规模路线。持续关注 Engineering at Meta、ai.meta.com/blog、OCP 与 Llama Stack 的发布，是跟上 AI 基础设施前沿的必要投入。
