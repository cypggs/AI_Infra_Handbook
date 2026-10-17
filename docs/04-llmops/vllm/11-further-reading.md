# 11. 延伸阅读

## 官方文档

- [vLLM 官方文档](https://docs.vllm.ai/)
- [vLLM V1 引擎指南](https://docs.vllm.ai/en/stable/usage/v1_guide)
- [vLLM GitHub Repository](https://github.com/vllm-project/vllm)
- [vLLM Release Notes](https://github.com/vllm-project/vllm/releases)

## 论文

- [PagedAttention: Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180) — SOSP 2023
- [Mooncake: A KVCache-centric Disaggregated Architecture for LLM Serving](https://arxiv.org/abs/2407.00079) — FAST 2025 最佳论文，PD 分离与 KV 池的生产级参考实现
- [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437) — MTP 与 EPLB（专家负载均衡）的出处
- [EAGLE: Speculative Sampling Requires Rethinking Feature Uncertainty](https://arxiv.org/abs/2401.15077) 与 EAGLE-3 — 推测解码主流草稿方案

## 官方博客（2025–2026 精选，均可在 [vLLM 官方博客](https://vllm.ai/blog)按标题检索）

- Tiered KV Cache Offloading in vLLM — 分层 KV 卸载设计与实测（2026-09-10），另见 [直接链接](https://vllm-project.github.io/2026/09/10/tiered-kv-offloading.html)
- Taking vLLM Apart: A Practical Guide to Disaggregated Serving — PD 分离部署指南（2026-09-29）
- vLLM Large Scale Serving: DeepSeek @ 2.2k tok/s/H200 with Wide-EP — 宽 EP 大规模 serving（2025-12-17）
- Zero-Reload Model Switching with vLLM Sleep Mode — Sleep Mode（2025-10-26）
- Native RL APIs in vLLM — RL rollout 集成（2026-05-28）
- Kimi K3 Performance Optimizations in vLLM: The Road to 2.8× Throughput — 大模型专项优化案例（2026-09-13）
- Structured Decoding in vLLM: a gentle introduction — xgrammar 结构化输出原理（2025-01-14）
- No More Train-Inference Mismatch: Bitwise Consistent On-Policy Reinforcement Learning with vLLM and TorchTitan（2025-11-10）

## 官方博客

- [vLLM Blog](https://blog.vllm.ai/)
- [Efficiently Scaling Transformer Inference](https://arxiv.org/abs/2211.05102)

## 技术演讲

- vLLM at KubeCon / Ray Summit / NVIDIA GTC
- LMSYS 团队关于 PagedAttention 的分享

## 对比与生产实践

- [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104)
- [TensorRT-LLM User Guide](https://nvidia.github.io/TensorRT-LLM/)
- [HuggingFace Text Generation Inference](https://github.com/huggingface/text-generation-inference)
- Together AI、Fireworks AI 官方技术博客

## 社区资源

- vLLM GitHub Discussions
- vLLM Slack / Discord
- vLLM 中文社区讨论

## 相关章节

- [LLMOps 概述](/04-llmops/)
- [RL Post-Training 基础设施详解](/04-llmops/rl-post-training/) — vLLM 是 RL rollout 的事实标准引擎（Native RL API、`sharded_rdt` 权重同步），本主题补全训练侧视角。
- [SGLang 详解](/04-llmops/sglang/)
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/)
- [Triton Inference Server 详解](/04-llmops/triton/)
- [LLM Gateway 详解](/04-llmops/llm-gateway/)
- [LLM 推理缓存与 KV Cache 管理详解](/04-llmops/kv-cache/) — KV 分层、PD 分离传输与 prefix 复用的基础设施视角，与 vLLM KV connector/BlockTable 互为表里。
- [多模态与语音推理基础设施详解](/04-llmops/multimodal-inference/) — multi_modal_data 占位符、内容哈希缓存与视觉编码器调度的基础设施视角。
- [模型量化与压缩基础设施详解](/04-llmops/model-quantization/) — AWQ/GPTQ/FP8 等量化方案的支持矩阵、精度-性能权衡与工具链，从压缩视角补全 vLLM 推理成本优化地图。
- [KServe 详解](/03-ai-platform/kserve/) — Kubernetes 模型服务平台，vLLM 是其核心 LLM runtime 之一，了解 KServe 可补全"从容器到服务"的平台视角。
- [Ray 详解](/03-ai-platform/ray/) — Ray Serve LLM 默认以 vLLM 作为推理后端，了解 Ray 可补充分布式服务与训练视角。
- [Kubernetes 详解](/02-cloud-native/kubernetes/) — vLLM 生产部署在 K8s 上，通过 Deployment + GPU 资源声明 + HPA 扩缩、探针/滚动升级管理生命周期，理解 K8s 是 vLLM 落地的基础。
- [GPU 在 Kubernetes 上的调度详解](/02-cloud-native/gpu-scheduling/) — vLLM 生产部署依赖 K8s GPU 调度、MIG/MPS、拓扑感知与 Gang 调度，本主题补全集群层面 GPU 治理视角。
- [学习路线](/10-roadmap/learning-path)
- [面试指南](/10-roadmap/interview-guide)
- [OpenAI 案例研究](/09-case-study/openai/) — 观察 PagedAttention/vLLM 类技术在大规模生产系统中的落地形态。
- [Anthropic 案例研究](/09-case-study/anthropic/) — prompt caching（prefix hash + 20-block lookback）是工程化 KV/prefix cache 的代表实践。
- [Meta 案例研究](/09-case-study/meta/) — Meta 是 PyTorch 主要贡献者，vLLM 是 Llama 推理事实标准，MTIA 提供 vLLM plugin backend；Llama Stack 标准化推理接口。

## 推荐学习路径

1. 先读 PagedAttention 论文，理解设计动机
2. 再读 vLLM 官方文档的 Architecture 和 Scheduling 部分
3. 然后阅读源码中的 `llm_engine.py` 和 `scheduler.py`
4. 最后结合生产实践文章，思考如何在自己的场景中部署
