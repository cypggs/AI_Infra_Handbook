# 11. 延伸阅读

## 11.1 一手论文（按主题分组）

**模型与训练：**
- [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437)（2024-12）——本主题的.primary 来源：MLA、DeepSeekMoE、DualPipe（Table 2）、跨节点 all-to-all、FP8 训练（§3.3 + 附录 B）、推理部署（§3.4）、硬件建议（§3.5）、成本表（Table 1）。
- [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948)（2025-01）——R1-Zero 的涌现曲线、GRPO、四阶段 pipeline、蒸馏与 MIT 许可。
- [DeepSeek-V3.2: Pushing the Frontier of Open Large Language Models](https://arxiv.org/abs/2512.02556)（2025-12）——DSA、943.7B tokens 稀疏训练、可扩展 RL 框架、agentic 任务合成、Speciale。
- [DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence](https://arxiv.org/abs/2606.19348)（2026）——V4-Pro（1.6T/49B）与 V4-Flash（284B/13B）、CSA+HCA 混合注意力、Muon 优化器、32T+ tokens。

**基础设施：**
- [Fire-Flyer AI-HPC: A Cost-Effective Software-Hardware Co-Design for Deep Learning](https://arxiv.org/abs/2408.14158)（SC'24）——1 万 PCIe A100、成本减半、HFReduce/HaiScale/3FS/HAI-Platform 的前身故事。
- [Insights into DeepSeek-V3: Scaling Challenges and Reflections on Hardware for AI Architectures](https://arxiv.org/abs/2505.09343)（ISCA'25 industry track）——从用户视角给硬件厂商的建议清单。
- [DeepSeek-V3.2-Exp 技术报告](https://github.com/deepseek-ai/DeepSeek-V3.2-Exp)（2025-09，GitHub PDF）——DSA 的首发验证，训练配置刻意对齐 V3.1-Terminus。

## 11.2 开源仓库（截至 2026-10 均在维护）

| 仓库 | 内容 | 特别推荐 |
|---|---|---|
| [deepseek-ai/DeepEP](https://github.com/deepseek-ai/DeepEP) | EP 通信库（EPBuffer/dispatch/combine） | V2.5 的动态冗余专家 API、Ascend 后端 |
| [deepseek-ai/DeepGEMM](https://github.com/deepseek-ai/DeepGEMM) | FP8/FP4 GEMM + MoE + indexer kernel | News 区的性能演进时间线（1350→1550 TFLOPS…） |
| [deepseek-ai/FlashMLA](https://github.com/deepseek-ai/FlashMLA) | MLA/DSA 注意力 kernel | `docs/` 下的 kernel deep-dive 与昇腾移植报告 |
| [deepseek-ai/3FS](https://github.com/deepseek-ai/3fs) | 并行文件系统 | design notes + USRBIO 文档 |
| [deepseek-ai/DualPipe](https://github.com/deepseek-ai/DualPipe) | 双向流水线算法 | 与论文 Figure 4/5 对照读 |
| [deepseek-ai/eplb](https://github.com/deepseek-ai/eplb) | EP 负载均衡 | 部署侧均衡的参考实现 |
| [deepseek-ai/smallpond](https://github.com/deepseek-ai/smallpond) | 3FS 上的数据处理 | DuckDB 集成范式 |
| [deepseek-ai/open-infra-index](https://github.com/deepseek-ai/open-infra-index) | 开源周索引 + 推理系统概览 | Day-6 的 545% 利润率原文口径 |
| [deepseek-ai/profile-data](https://github.com/deepseek-ai/profile-data) | V3/R1 计算通信重叠 profiling | 训练通信实测的公开数据 |

## 11.3 官方文档与公告

- [DeepSeek API 文档 · Change Log](https://api-docs.deepseek.com/updates/)——版本时间线的权威来源（V3/R1/V3.1/V3.2-Exp/V3.2/V4/V4.1 的上线日期与定价变更）。
- [Introducing DeepSeek-V3.2-Exp](https://api-docs.deepseek.com/news/news250929/)（2025-09-29）——DSA 发布与 API 降价公告。
- [DeepSeek 官方站点](https://www.deepseek.com/) 与 [Hugging Face 组织页](https://huggingface.co/deepseek-ai)——权重与模型卡。

## 11.4 手册内交叉引用

**其他案例研究（对照阅读）：**
- [OpenAI 案例研究](/09-case-study/openai/)——闭源规模路线的对照组；"成本函数公开"冲击的对象。
- [Google 案例研究](/09-case-study/google/)——TPU 垂直整合 vs 受限 GPU + 自研框架；Pathways 与 HAI-LLM 的框架哲学对照。
- [Meta 案例研究](/09-case-study/meta/)——两条开放路线：权重+硬件开放 vs 权重+全栈开放。
- [Anthropic 案例研究](/09-case-study/anthropic/)——闭源安全路线的对照。
- [xAI 案例研究](/09-case-study/xai/)——新兴实验室的算力建设路线对照。

**基础设施主题：**
- [分布式系统基础](/01-foundation/distributed-systems/)——流水线调度、all-to-all、ZeRO、CRAQ 的理论底座。
- [存储系统](/01-foundation/storage-systems/)——3FS 的复制协议与一致性设计背景。
- [计算机网络](/01-foundation/computer-networks/)——NVLink/IB 两级模型、RDMA、多平面拓扑。
- [GPU 与 CUDA](/01-foundation/gpu-cuda/)——WGMMA、SM 架构、kernel 优化基础。
- [推理服务 vLLM](/04-llmops/vllm/) 与 [SGLang](/04-llmops/sglang/)——PD 分离、分页 KV、调度策略的对照实现（SGLang 已集成 3FS KV 后端）。
- [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/)——DeepJIT/TileLang 与 kernel 生成主题互为印证。
- [AI SRE](/07-ai-sre/)——训练零回滚、故障域设计的运维视角。
- [AI 安全](/08-security/)——开源权重的治理议题。

## 11.5 阅读路径建议

- **只有 30 分钟**：V3 论文 §1（引言与成本表）→ §3.2（DualPipe + all-to-all）→ 本主题 [第 5 章](05-core-modules)。
- **想复现机制**：[Mini Demo](07-mini-demo) 五个场景 → DeepGEMM 的 News 区 → FlashMLA 的 deep-dive 文档。
- **做硬件/采购决策**：ISCA'25 论文 → V3 §3.5 硬件建议 → [第 8 章](08-production-practice) 的算力约束时间线。
