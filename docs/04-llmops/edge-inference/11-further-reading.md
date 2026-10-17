---
title: 11. 延伸阅读
---

# 11. 延伸阅读

## 11.1 论文

- **《Fast Inference from Transformers via Speculative Decoding》**（Leviathan et al., ICML 2023）：投机解码的奠基论文，期望加速比公式的来源。
- **《LLM in a flash: Efficient Large Language Model Inference with Limited Memory》**（Apple 机器学习研究团队，2024）：有限内存下的流式推理与稀疏激活加载，第 2 章「热子集」思想的出处。
- **《MLC LLM: Universal LLM Deployment Engine with ML Compilation》**（2023）：TVM 编译路线的方法论，static memory planning 的范本。
- **《ExecuTorch: An End-to-End Solution for On-Device AI》**（Meta，2024）：PyTorch 官方端侧栈的设计白皮书，delegate 架构细节。
- **Medusa / EAGLE 系列**（2023-2024）：免 draft 模型与高质量 draft 头的两条投机解码演进路线。

## 11.2 一手文档与版本锚点

| 资源 | 锚点（截至 2026-10） |
|---|---|
| llama.cpp Releases | v0.7.0（2026-10-15），ggml v0.27.0，github.com/ggml-org/llama.cpp |
| ExecuTorch Releases | v1.5.1（2026-09-23），QNN/Core ML/XNNPACK 三线，github.com/pytorch/executorch |
| ONNX Runtime Releases | v1.31.0（2026-10-09），github.com/microsoft/onnxruntime |
| MLX Releases | v0.32.4（2026-10-14），github.com/ml-explore/mlx |
| coremltools | 9.x 稳定版，github.com/apple/coremltools |
| Apple Security Blog: Private Cloud Compute | 2024-06-10 发布，security.apple.com/blog/private-cloud-compute/ |
| NVIDIA JetPack 归档 | JetPack 7.2.1（L4T 39.2.1）/ 6.2.3（L4T 36.5.2），developer.nvidia.com/embedded/jetpack-archive |
| Qualcomm AI Engine Direct SDK | QNN delegate 官方文档，developer.qualcomm.com |

## 11.3 相关章节

- [vLLM](/04-llmops/vllm/)：云端 serving 的架构参照系——continuous batching、PagedAttention 与端侧静态纪律的镜像对照。
- [模型量化与压缩基础设施](/04-llmops/model-quantization/)：量化算法的上游——本主题的 GGUF/ONNX 格式消费它的 PTQ/QAT 产物与误差结论。
- [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/)：ExecuTorch/MLC 的「导出-变换-lower」管线是编译器思想在端侧的落地。
- [多模态与语音推理基础设施](/04-llmops/multimodal-inference/)：语音助手与视觉理解的端侧形态，流式低延迟要求与本主题叠加。
- [LLM 推理缓存与 KV Cache 管理](/04-llmops/kv-cache/)：KV 复用、量化与驱逐的完整理论，端侧只取「容量规划 + 量化」子集。
- [GPU 与 CUDA 编程](/01-foundation/gpu-cuda/)：roofline 模型与统一内存语义的硬件基础。
- [Personal AI Agent](/05-agent/personal-agent/)：端侧推理是个人 Agent 的执行底座，隐私与离线能力定义了产品边界。
- [安全](/08-security/)：模型供应链签名、端云数据边界与 PCC 可验证性的安全视角。

## 11.4 社区与实践

- llama.cpp 的 GitHub Discussions 与示例目录：gguf 量化参数、后端启用方式的第一手资料。
- ExecuTorch 官方示例（llama demo、QNN 后端教程）：Android 正式产品的落地模板。
- Apple MLX 示例仓库（mlx-lm）：Apple Silicon 上推理/微调的最短路径。
- Jetson AI Lab：边缘 LLM 部署的机型级教程与基准。
