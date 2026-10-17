# 模型量化与压缩基础设施 总览

> 一句话理解：**模型量化把「模型该用什么数值表示」从一个训练时的超参数，变成了一条可独立交付的基础设施管线**——导出、校准、压缩、校验、封装、部署，每个环节都有独立的工具、算法与工程决策，其产出物（量化格式 + kernel）直接决定推理引擎能跑多快、多省、多准。

## 学习目标

阅读完本主题后，你应该能够：

1. 用「符号位 + 指数位 + 尾数位」的框架解释 FP8 E4M3/E5M2、FP4 E2M1 的表示范围，并说明为什么 INT4 必须有 scale 而 FP4 必须有 block scale。
2. 手算对称/非对称、per-tensor/per-channel/group-wise 的量化与反量化，并推导 group-wise 的等效位宽（4 + 16/g bits/weight）。
3. 讲清 PTQ / QAT / QAFT 三条路线的成本与精度差异，并能按场景选型。
4. 说清楚 AWQ、GPTQ、SmoothQuant、KIVI 各自解决了什么问题、依赖什么校准信息、误差补偿/难度迁移的机制。
5. 画出从 FP 模型到线上推理的完整量化管线（导出 → 校准 → 压缩 → 校验 → 封装 → 部署），并标注每个环节的输入输出。
6. 对比 llm-compressor、NVIDIA Model Optimizer（Quark）、GPTQModel、llama.cpp 量化器的定位与产出格式。
7. 读懂 vLLM / TensorRT-LLM / SGLang 的量化支持矩阵，按 GPU 代际选格式（Blackwell → NVFP4，Hopper → FP8，Ampere → INT4 W4A16）。
8. 跑通并扩展本主题的 Mini Demo（量化误差对比、group size 权衡、平滑迁移、GPTQ 补偿、KV 量化、FP4/FP8 格式模拟）。
9. 回答量化精度评估、速度-显存-精度三角、线上灰度相关的面试问题。

## 与 LLMOps 其他主题的关系

引擎类主题（vLLM、SGLang、TensorRT-LLM）回答的是「量化后的模型怎么跑得最快」，本主题回答的是「模型怎么变成那个量化格式」——两者通过量化格式与 kernel 契约对接。

| 主题 | 解决的核心问题 | 与本主题的关系 |
|---|---|---|
| [vLLM](/04-llmops/vllm/) | 单引擎高吞吐 serving | 消费 compressed-tensors / AWQ / GPTQ / GGUF / FP8 等量化产物；Marlin 等 kernel 的宿主 |
| [SGLang](/04-llmops/sglang/) | LLM Program 与结构化生成 | 支持 mxfp4 / nvfp4_online / modelopt_fp4 等新格式的最快跟进者之一 |
| [TensorRT-LLM](/04-llmops/tensorrt-llm/) | NVIDIA 编译型推理引擎 | Model Optimizer 量化产物的原生消费方；NVFP4 KV cache 的落地引擎 |
| [Triton Inference Server](/04-llmops/triton/) | 多框架统一推理服务 | 部署形态参考；量化模型经 backend 接入 |
| [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/) | 算子与 Kernel 优化 | 量化 kernel（Marlin/CUTLASS/DeepGEMM）属于编译层的最终交付物；FP8/FP4 需要 tensor core 指令级配合 |
| [LLM 推理缓存与 KV Cache 管理](/04-llmops/kv-cache/) | KV 复用、迁移与分层 | KV cache 量化（FP8/INT4）是量化基础设施向运行时状态的延伸 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 多引擎统一接入与治理 | 灰度发布与按量化版本路由的落地位置 |
| [从零训练大模型](/01-foundation/llm-from-zero/) | 训练流程与数值基础 | BF16/FP8 混合精度训练是量化精度的「上游」；QAFT 依赖它 |
| [GPU 与 CUDA 编程](/01-foundation/gpu-cuda/) | GPU 体系结构与编程模型 | tensor core 低精度指令（INT8/FP8/FP4 MMA）决定量化收益上限 |

## 本章结构

1. [背景](01-background) — 显存墙与带宽墙：为什么量化是推理的第一杠杆。
2. [核心思想](02-core-ideas) — 数值表示、舍入、缩放与难度迁移。
3. [架构设计](03-architecture) — 量化管线的六个环节与反馈回路。
4. [工作流程](04-quantization-workflow) — 一次 AWQ 量化的完整流程。
5. [核心模块](05-core-modules) — 校准器、压缩算法、格式封装与 kernel 后端。
6. [生态与源码分析](06-ecosystem-analysis) — GPTQ / AWQ / SmoothQuant / Quark / llm-compressor / llama.cpp 横向对比。
7. [Mini Demo](07-mini-demo) — 纯 Python 可运行的六类机制模拟。
8. [企业生产实践](08-production-practice) — 选型决策、精度回归与线上灰度。
9. [最佳实践](09-best-practices) — 位宽粒度、校准集、敏感层保护清单。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 论文、官方文档与手册内回链。

## 一句话总结

模型量化与压缩基础设施把「低精度化」从论文算法变成工程管线：**校准把数据变成统计量，算法把统计量变成补偿与迁移，格式封装把权重新排列成 kernel 爱吃的形状，kernel 后端决定这些比特最终能跑多快**——速度、显存、精度的三角权衡，就浓缩在管线每个环节的具体选择里。
