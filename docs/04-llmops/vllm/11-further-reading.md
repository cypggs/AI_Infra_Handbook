# 11. 延伸阅读

## 官方文档

- [vLLM 官方文档](https://docs.vllm.ai/)
- [vLLM V1 引擎指南](https://docs.vllm.ai/en/stable/usage/v1_guide)
- [vLLM GitHub Repository](https://github.com/vllm-project/vllm)
- [vLLM Release Notes](https://github.com/vllm-project/vllm/releases)

## 论文

- [PagedAttention: Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180) — SOSP 2023

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
- [SGLang 详解](/04-llmops/sglang/)
- [TensorRT-LLM 详解](/04-llmops/tensorrt-llm/)
- [Triton Inference Server 详解](/04-llmops/triton/)
- [LLM Gateway 详解](/04-llmops/llm-gateway/)
- [学习路线](/10-roadmap/learning-path)
- [面试指南](/10-roadmap/interview-guide)
- [OpenAI 案例研究](/09-case-study/openai/) — 观察 PagedAttention/vLLM 类技术在大规模生产系统中的落地形态。

## 推荐学习路径

1. 先读 PagedAttention 论文，理解设计动机
2. 再读 vLLM 官方文档的 Architecture 和 Scheduling 部分
3. 然后阅读源码中的 `llm_engine.py` 和 `scheduler.py`
4. 最后结合生产实践文章，思考如何在自己的场景中部署
