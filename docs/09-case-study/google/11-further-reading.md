# 11. 延伸阅读

本章给出 Google 案例的一手来源（论文、仓库、博客）、按主题分组，以及与手册其它主题的交叉引用和学习路径建议。原链接于 2026-07-03 核验；2026-10-17 更新补充了 TPU 8t/8i（Cloud Next '26）、Gemma 4、Gemini 3、Anthropic/Meta 算力协议等新来源（新增行已注明日期与来源级别）；2026-10-18 增量补充 Alphabet Q2 FY2026 财报 capex 指引（2026-07 窗口内的一手财报数据）。

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
| **Gemma 4 技术报告** | arXiv:2607.02770（2026-07） | [arxiv.org/abs/2607.02770](https://arxiv.org/abs/2607.02770) |
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
| **Ironwood（TPU v7）发布** | Google 官方博客（2025-04） | [blog.google/.../ironwood-tpu-age-of-inference](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/ironwood-tpu-age-of-inference/) / [blog.google/.../ironwood-google-tpu-things-to-know](https://blog.google/products/google-cloud/ironwood-google-tpu-things-to-know/) |
| **TPU 8t/8i 与 Virgo（Cloud Next '26）** | Google 主题演讲（2026-04-22/23）；二手详报 [StorageReview](https://www.storagereview.com/news/google-announces-tpu-8t-sunfish-and-tpu-8i-zebrafish)、[aipedia.wiki](https://aipedia.wiki/news/2026-04-22-google-ironwood-tpu-cloud-next-2026/) | 官方 blog 汇总页检索 "TPU 8t 8i"；规格以主题演讲为准 |
| **投机解码（DFlash，~3×）** | Google Developers 博客（2026-05） | [developers.googleblog.com/.../supercharging-llm-inference-...-speculative-decoding](https://developers.googleblog.com/supercharging-llm-inference-on-google-tpus-achieving-3x-speedups-with-diffusion-style-speculative-decoding/) |
| **Gemma 4 MTP drafter** | Google AI 发布说明（2026-05，经 [MarkTechPost 报道](https://www.marktechpost.com/2026/05/06/google-ai-releases-multi-token-prediction-mtp-drafters-for-gemma-4-delivering-up-to-3x-faster-inference-without-quality-loss/)） | Hugging Face `google/gemma-4-*` |
| **JAX 分布式数组与自动并行** | JAX 官方文档 | [docs.jax.dev/.../Distributed_arrays_and_automatic_parallelization.html](https://docs.jax.dev/en/latest/notebooks/Distributed_arrays_and_automatic_parallelization.html) |
| **Gemini API / Vertex AI** | — | [ai.google.dev](https://ai.google.dev/) / [cloud.google.com/vertex-ai](https://cloud.google.com/vertex-ai) |
| **Gemini 3 企业可用** | Google Cloud 博客（2025-11） | [cloud.google.com/blog/products/ai-machine-learning/gemini-3-is-available-for-enterprise](https://cloud.google.com/blog/products/ai-machine-learning/gemini-3-is-available-for-enterprise) |
| **Anthropic × Google × Broadcom 算力协议** | Anthropic 官方新闻（2026-04） | [anthropic.com/news/google-broadcom-partnership-compute](https://www.anthropic.com/news/google-broadcom-partnership-compute) |
| **Meta TPU 协议** | [SiliconANGLE 报道](https://siliconangle.com/2026/02/26/google-meta-reportedly-strike-new-multibillion-dollar-ai-chip-deal/)（2026-02，二手） | 双方无正式公告 |
| **Alphabet 2026 capex 指引（$195B–$205B）** | Q2 FY2026 财报解读（2026-07，[Futurum Group](https://futurumgroup.com/insights/alphabet-q2-fy-2026-google-cloud-leads-growth-amid-rising-ai-investment/)）；初版指引 [Reuters](https://www.reuters.com/business/google-parent-alphabet-forecasts-sharp-surge-2026-capital-spending-2026-02-04/)（2026-02） | abc.xyz investor relations |

---

## 11.3 可读源码（开源仓库）

| 项目 | 仓库 | 用途 |
|---|---|---|
| **MaxText** | [AI-Hypercomputer/maxtext](https://github.com/AI-Hypercomputer/maxtext) | 最易读的 TPU 训练参考实现（JAX）；本案例 [第 6 章](06-source-analysis) 的主要源码来源 |
| **JAX** | [jax-ml/jax](https://github.com/jax-ml/jax) | 函数式可追踪前端；GSPMD 的载体 |
| **XLA / OpenXLA** | [openxla/xla](https://github.com/openxla/xla) | 编译器（含 GSPMD 分片 pass） |
| **JetStream / tpu-inference** | [AI-Hypercomputer/JetStream](https://github.com/AI-Hypercomputer/JetStream) → `tpu-inference` | TPU 原生推理引擎 |
| **MaxDiffusion** | [AI-Hypercomputer/maxdiffusion](https://github.com/AI-Hypercomputer/maxdiffusion) | 扩散模型训练参考 |
| **Gemma** | [HF google/gemma-3](https://huggingface.co/google/gemma-3) / `google/gemma-4-*` / [ai.google.dev/gemma](https://ai.google.dev/gemma) | 开放权重模型（3 代为 Gemma Terms of Use，4 代起 Apache-2.0） |
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
| **DeepSeek 案例** | 对照"自研硅垂直整合" vs "受限 GPU + 算法-系统协同设计" | [/09-case-study/deepseek/](/09-case-study/deepseek/) |
| **xAI 案例** | 对照"十年 TPU 演进" vs "122 天 Colossus 单园区速度战" | [/09-case-study/xai/](/09-case-study/xai/) |
| **Perplexity 案例** | 对照"自研硅垂直整合" vs "不训模型、推理经济学+模型无关主义" | [/09-case-study/perplexity/](/09-case-study/perplexity/) |

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
- **TPU 8t/8i 与 Virgo 的具体规格**：来自 2026-04 Cloud Next 主题演讲与二手报道，是**未出货硅片的官方预期指标**；GA 时间官方口径（2026–2027 分批）与部分分析报道（更晚）不一致。
- **Gemini 3 的具体训练代际（是否 Ironwood）**：官方仅确认"在新一代 TPU 上训练 Gemini"，具体代际为第三方报道。
- **Anthropic $200B / Meta TPU 协议金额**：一手公告之外的高额数字为媒体报道，未见双方正式确认。
- **Gemini 具体训练/服务 ops 数字**：非公开，本案例未引用具体值。
- **NSDI'24 术语**：论文无 "cherry-pick"/"performance health"/"functional health"；本案例一律用论文真实术语（end-to-end check / intent-driven checker / reconfigure / fault-tolerant ICI routing），详见 [第 2 章](02-core-ideas) 与 [第 8 章](08-production-practice)。

> 如发现链接失效或数字有更新，欢迎在仓库提 issue 修正。本案例的开放姿态本身就是"可学习、可纠错"的——正如 Google 开放其软件栈的初衷。
