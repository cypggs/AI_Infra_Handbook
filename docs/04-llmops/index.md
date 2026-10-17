# LLMOps 篇

本章节覆盖大模型推理、部署与服务的工程实践。

## 已上线主题

- [vLLM](/04-llmops/vllm/)：开源高性能 LLM 推理引擎
- [SGLang](/04-llmops/sglang/)：面向 LLM Program 的推理引擎，强调 RadixAttention 与结构化生成
- [TensorRT-LLM](/04-llmops/tensorrt-llm/)：NVIDIA 高性能编译型 LLM 推理引擎
- [Triton Inference Server](/04-llmops/triton/)：NVIDIA 开源多框架推理服务软件，统一承载多种推理后端
- [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/)：从 torch.compile/Inductor 到 Triton 语言、cuTile/CUTLASS、TileLang 与 Mirage——算子编译与 GPU Kernel 生成层
- [LLM 推理缓存与 KV Cache 管理](/04-llmops/kv-cache/)：KV Cache 作为新兴存储对象的分层、迁移与复用——PD 分离、Mooncake/LMCache/NIXL、prefix 路由与卸载
- [多模态与语音推理基础设施](/04-llmops/multimodal-inference/)：VLM 推理与实时语音链路——统一 token 调度、VAD/打断/双工、first-audio 延迟预算
- [模型量化与压缩基础设施](/04-llmops/model-quantization/)：从校准到部署的量化工具链——GPTQ/AWQ/SmoothQuant、FP8/NVFP4/MXFP4 格式与 kernel 后端
- [LLM Gateway](/04-llmops/llm-gateway/)：位于客户端与推理后端之间的访问控制与抽象层
- [RL Post-Training 基础设施](/04-llmops/rl-post-training/)：把强化学习闭环跑在千卡集群上的工程系统，覆盖 GRPO/PPO、Rollout/Train 分离、veRL/OpenRLHF 源码与生产实践

## 计划中主题

> 暂无明确计划，后续会根据社区反馈补充 LLMOps 周边主题。

## 一句话理解

> LLMOps 的核心问题：在有限的 GPU 显存和算力下，以最低的延迟和最高的吞吐服务大模型。

从 vLLM/SGLang/TensorRT-LLM 等推理引擎，到 KV Cache 管理、模型量化、多模态与语音推理，再到 AI 编译器与 RL Post-Training，LLMOps 篇已覆盖推理全链路的主要基础设施主题。
