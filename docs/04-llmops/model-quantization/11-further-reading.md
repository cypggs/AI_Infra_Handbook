# 11. 延伸阅读

> 一句话理解：量化知识分布在四处——**论文**（机制思想的源头）、**规范**（格式的法定定义）、**工具文档**（工程真相随版本变化最快）与**手册相邻主题**（部署与运行时）；按「先建立机制直觉，再核对当前版本支持」的顺序读。

## 论文

- **GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers**（Frantar et al., 2022, arXiv:2210.17323）：OBS 逐列误差补偿的奠基作，3-4 bit 时代的算法基线。
- **AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration**（Lin et al., MLSys 2024, arXiv:2306.00978）：缩放搜索 + 1% salient 通道保护，W4A16 生产主力。
- **SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models**（Xiao et al., ICML 2023, arXiv:2211.10438）：难度迁移，W8A8 与 FP8 scale 管理的思想源头。
- **LLM.int8()**（Dettmers et al., 2022）与 **QLoRA**（2023）：outlier 混合分解与 NF4，训练/微调侧量化必读。
- **KIVI: A Tuning-Free Asymmetric 2bit Quantization for KV Cache**（Liu et al., ICML 2024）：K 按通道、V 按 token 的不对称 KV 量化，Mini Demo 场景 5 的出处。
- **QuIP#**（Tseng et al., 2024）与 **QuaRot / SpinQuant**：随机 Hadamard 旋转 + 格码本，2-bit 研究前沿。
- **DeepSeek-V3 技术报告**（2024）：FP8 混合精度训练与细粒度缩放的全链路工程范本。

## 规范与格式定义

- **OCP Microscaling Formats (MX) v1.0 规范**：MXFP8/6/4 的官方定义（32 元素块 + E8M0 共享 scale）——理解 MXFP4 与 NVFP4 差异的法定出处。
- **GGUF 规范**（ggml 仓库 `docs/gguf.md`）：自描述元数据、K-quants 类型枚举（Q4_K_M、IQ4_XS、MXFP4 等）与版本演进。
- **OCP FP8 规范（E4M3/E5M2）**：S.1111.111 为 NaN 等位级细节。

## 官方文档与开源项目（版本信息截至 2026-10）

- llm-compressor：<https://github.com/vllm-project/llm-compressor>（v0.13.0：Triton GPTQ kernel、MoE batched GPTQ、FP4 observer）
- NVIDIA Model Optimizer：<https://github.com/NVIDIA/TensorRT-Model-Optimizer>（2025-12 起由 TensorRT Model Optimizer 更名；AutoQuant KV）
- GPTQModel：<https://github.com/ModelCloud/GPTQModel>（AutoGPTQ 接班者）
- llama.cpp 量化器与 imatrix：<https://github.com/ggerganov/llama.cpp>
- AutoAWQ（已归档，2025-05）：<https://github.com/casper-hansen/AutoAWQ>
- vLLM 量化支持矩阵：<https://docs.vllm.ai/en/latest/features/quantization/>
- SGLang 量化文档：<https://docs.sglang.io/advanced_features/quantization.html>
- TensorRT-LLM 量化特性：<https://nvidia.github.io/TensorRT-LLM/features/quantization.html>

## 手册内回链

### 引擎层（量化产物的消费方）

- [vLLM](/04-llmops/vllm/) — compressed-tensors / AWQ / GPTQ / GGUF 的原生消费方；Marlin kernel 宿主
- [SGLang](/04-llmops/sglang/) — mxfp4 / nvfp4_online / modelopt_fp4 等新格式的最快跟进者
- [TensorRT-LLM](/04-llmops/tensorrt-llm/) — Quark 量化产物与 NVFP4 KV cache 的落地引擎
- [Triton Inference Server](/04-llmops/triton/) — 部署形态参考

### 相邻基础设施层

- [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/) — Marlin/CUTLASS/DeepGEMM 的编译视角；FP8/FP4 的 tensor core 指令配合
- [LLM 推理缓存与 KV Cache 管理](/04-llmops/kv-cache/) — KV 量化（FP8/INT4）是量化向运行时状态的延伸
- [LLM Gateway](/04-llmops/llm-gateway/) — 量化版本的灰度路由与回退落地位置
- [端侧与边缘推理基础设施](/04-llmops/edge-inference/) — GGUF/Q4_K_M 与 NPU 激活量化的消费侧；端侧 KV 量化（INT8/INT4）的容量账

### 基础层

- [从零训练大模型](/01-foundation/llm-from-zero/) — BF16/FP8 混合精度训练是量化精度的上游；QAFT 的载体
- [GPU 与 CUDA 编程](/01-foundation/gpu-cuda/) — tensor core 低精度指令集决定量化收益上限
