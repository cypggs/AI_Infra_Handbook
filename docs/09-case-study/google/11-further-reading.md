# 11. 延伸阅读

本章给出 Google 案例的一手来源（论文、仓库、博客）、按主题分组，以及与手册其它主题的交叉引用和学习路径建议。所有链接于 2026-07-03 核验。

---

## 11.1 核心论文（一手）

| 主题 | 论文 / 来源 | 链接 |
|---|---|---|
| **TPU v4 可靠性** | NSDI'24《Resiliency at Scale: Managing Google's TPUv4 ML Supercomputer》, Zu et al. | [usenix.org/system/files/nsdi24-zu.pdf](https://www.usenix.org/system/files/nsdi24-zu.pdf) |
| **Borg 集群管理** | EuroSys'15《Large-scale cluster management at Google with Borg》 | [research.google/pubs/archive/43438.pdf](https://research.google/pubs/archive/43438.pdf)（用 `research.google` 非 `.com`） |
| **Pathways 运行时** | MLSys'22《Pathways: Asynchronous Distributed Dataflow for ML》, arXiv:2203.12533 | [arxiv.org/abs/2203.12533](https://arxiv.org/abs/2203.12533) |
| **GSPMD 自动分片** | arXiv:2105.04663《GSPMD: General and Scalable Parallelization for ML Computation Graphs》 | [arxiv.org/abs/2105.04663](https://arxiv.org/abs/2105.04663) |
| **TPU v1 架构** | Jouppi et al.《In-Datacenter Performance Analysis of a Tensor Processing Unit》 | [arxiv.org/abs/1704.04760](https://arxiv.org/abs/1704.04760) |
| **TPU v4 架构（含 SparseCore/OCS）** | ISCA'23《TPU v4: An Optically Reconfigurable 3D Torus ...》 | [arxiv.org/abs/2304.01433](https://arxiv.org/abs/2304.01433) |
| **Gemma 3 技术报告** | arXiv:2503.19786 | [arxiv.org/html/2503.19786v1](https://arxiv.org/html/2503.19786v1) |
| **Falcon 硬件传输** | SIGCOMM'25（最佳论文） | [dl.acm.org/doi/10.1145/3718958.3754353](https://dl.acm.org/doi/10.1145/3718958.3754353)（ACM 付费墙；作者副本 [praveenk.io/papers/falcon.pdf](https://praveenk.io/papers/falcon.pdf)） |
| **Frontier Safety 评估套件** | Phuong et al.《Evaluating frontier models for dangerous capabilities》, 2024 | DeepMind 技术报告 |

---

## 11.2 官方博客与文档

| 主题 | 来源 | 链接 |
|---|---|---|
| **Multislice 跨 Pod 训练** | Cloud TPU Multislice 博客 | [cloud.google.com/blog/.../using-cloud-tpu-multislice-...](https://cloud.google.com/blog/products/compute/using-cloud-tpu-multislice-to-scale-ai-workloads) |
| **Falcon 传输** | Google Systems 博客 | [cloud.google.com/blog/topics/systems/introducing-falcon-...](https://cloud.google.com/blog/topics/systems/introducing-falcon-a-reliable-low-latency-hardware-transport) |
| **TPU 架构文档** | Cloud TPU 性能/架构文档 | [cloud.google.com/tpu/docs](https://cloud.google.com/docs/tpu) |
| **TPU 产品代次（v1–Ironwood）** | Google Cloud / DeepMind 博客 | [cloud.google.com/blog](https://cloud.google.com/blog/) 搜 "Ironwood" / "Trillium" |
| **投机解码（DFlash，~3×）** | Google Developers 博客（2026-05） | [developers.googleblog.com/.../supercharging-llm-inference-...-speculative-decoding](https://developers.googleblog.com/supercharging-llm-inference-on-google-tpus-achieving-3x-speedups-with-diffusion-style-speculative-decoding/) |
| **JAX 分布式数组与自动并行** | JAX 官方文档 | [docs.jax.dev/.../Distributed_arrays_and_automatic_parallelization.html](https://docs.jax.dev/en/latest/notebooks/Distributed_arrays_and_automatic_parallelization.html) |
| **Gemini API / Vertex AI** | — | [ai.google.dev](https://ai.google.dev/) / [cloud.google.com/vertex-ai](https://cloud.google.com/vertex-ai) |

---

## 11.3 可读源码（开源仓库）

| 项目 | 仓库 | 用途 |
|---|---|---|
| **MaxText** | [AI-Hypercomputer/maxtext](https://github.com/AI-Hypercomputer/maxtext) | 最易读的 TPU 训练参考实现（JAX）；本案例 [第 6 章](06-source-analysis) 的主要源码来源 |
| **JAX** | [jax-ml/jax](https://github.com/jax-ml/jax) | 函数式可追踪前端；GSPMD 的载体 |
| **XLA / OpenXLA** | [openxla/xla](https://github.com/openxla/xla) | 编译器（含 GSPMD 分片 pass） |
| **JetStream / tpu-inference** | [AI-Hypercomputer/JetStream](https://github.com/AI-Hypercomputer/JetStream) → `tpu-inference` | TPU 原生推理引擎 |
| **MaxDiffusion** | [AI-Hypercomputer/maxdiffusion](https://github.com/AI-Hypercomputer/maxdiffusion) | 扩散模型训练参考 |
| **Gemma** | [HF google/gemma-3](https://huggingface.co/google/gemma-3) / [ai.google.dev/gemma](https://ai.google.dev/gemma) | 开放权重模型 |
| **Pax / Paxml** | [google/paxml](https://github.com/google/paxml) | 大规模训练框架（维护/参考角色） |
| **T5X** | [google-research/t5x](https://github.com/google-research/t5x) | T5 风格 encoder-decoder 训练 |
| **Orbax / Optax / Flax / Grain / Tunix** | [google/orbax](https://github.com/google/orbax) 等 | MaxText 组合使用的依赖库 |

> Pathways 运行时**未开源**（内部系统，协调底座 PLAQUE 闭源）。

---

## 11.4 可持续性、安全与治理

| 主题 | 来源 | 链接 |
|---|---|---|
| **数据中心可持续（PUE/CFE）** | Google Data Centers | [datacenters.google/operating-sustainably](https://datacenters.google/operating-sustainably) |
| **运营可持续** | sustainability.google | [sustainability.google/operations](https://sustainability.google/operations/) |
| **AI Principles** | Google AI | [ai.google/principles](https://ai.google/principles/) |
| **Frontier Safety Framework** | DeepMind 博客 | [deepmind.google/blog/introducing-the-frontier-safety-framework](https://deepmind.google/blog/introducing-the-frontier-safety-framework/) |

---

## 11.5 与手册其它主题的交叉引用

| 主题 | 关联 | 链接 |
|---|---|---|
| **AI SRE** | NSDI'24 双路径恢复、healthd、preflight、99.98% 可用率是 AI SRE 硬核案例 | [/07-ai-sre/](/07-ai-sre/) |
| **AI 平台 / 算力底座** | TPU + GCP 是三大算力底座之一；Multislice 是跨 Pod 弹性算力代表 | [/03-ai-platform/](/03-ai-platform/) |
| **LLMOps / 推理服务** | JetStream/tpu-inference 是 TPU 原生推理；投机解码是推理加速代表 | [/04-llmops/](/04-llmops/) |
| **RAG / 向量检索** | SparseCore 为稀疏嵌入加速，与大规模检索 workload 相关 | [/06-rag/](/06-rag/) |
| **安全** | Frontier Safety Framework、AI Principles、PSP 传输加密 | [/08-security/](/08-security/) |
| **Meta 案例** | 对照"开放权重 + OCP 硬件 + PyTorch" vs "开放软件栈 + 自研 TPU + JAX" | [/09-case-study/meta/](/09-case-study/meta/) |
| **OpenAI 案例** | 对照"闭源规模 + 通用 GPU" vs "垂直整合自研硅 + 软件全开" | [/09-case-study/openai/](/09-case-study/openai/) |
| **Anthropic 案例** | 对照"闭源对齐" vs "开放生态 + 安全框架" | [/09-case-study/anthropic/](/09-case-study/anthropic/) |

---

## 11.6 建议学习路径

1. **先读 NSDI'24**（[PDF](https://www.usenix.org/system/files/nsdi24-zu.pdf)）：它是理解 Google 大规模训练可靠性的核心，OCS/3D-torus/双路径恢复都在里有量化数据。
2. **跑本案例的 [Mini Demo](07-mini-demo)**：亲手调整 torus 维度、故障率、reroute 步时惩罚，建立对"延迟项"与"双路径权衡"的直觉。
3. **读 MaxText 源码**：从 `src/maxtext/utils/sharding.py`（分片标注）与 `trainers/pre_train/train.py`（训练循环）入手，理解"标注即并行"如何落地。
4. **读 Pathways + GSPMD 论文**：理解运行时与编译器的分工（标注 → 分片 → 编排）。
5. **对照 Meta 案例**：把两个案例的"可靠性工程"（NSDI 双路径 vs SDC 治理）放一起，得到完整的"AI 数据中心可靠性"设计图。
6. **关注可持续与安全治理**：PUE 1.09、24/7 CFE、Frontier Safety Framework 是生产落地的硬约束。

---

## 11.7 未决/需进一步核实项

为保持严谨，本案例中以下项标注了来源限制（详见各章脚注）：

- **TPU 制程节点**（28/16/7/4/3 nm）：Google 主文档未披露，来自二手来源（Wikipedia/SemiAnalysis）。
- **Ironwood ICI**：Google 写 "1.2 TBps bidirectional"（字节、双向），= 9.6 Tbps 双向 / 4.8 Tbps 单向——勿误读为"每链路 1.2 Tbps"。
- **Gemma 3 "N 种语言"**：技术报告未在正文给出单一数字，仅称"扩大了多语言覆盖"。
- **Frontier Safety Framework v2.0 具体变更**：v2.0 PDF 未从博客 HTML 可达。
- **当前 24/7 CFE 百分比**：需查年度环境报告 PDF，页面未直接给数字。
- **Gemini 具体训练/服务 ops 数字**：非公开，本案例未引用具体值。
- **NSDI'24 术语**：论文无 "cherry-pick"/"performance health"/"functional health"；本案例一律用论文真实术语（end-to-end check / intent-driven checker / reconfigure / fault-tolerant ICI routing），详见 [第 2 章](02-core-ideas) 与 [第 8 章](08-production-practice)。

> 如发现链接失效或数字有更新，欢迎在仓库提 issue 修正。本案例的开放姿态本身就是"可学习、可纠错"的——正如 Google 开放其软件栈的初衷。
