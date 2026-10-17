# 多模态与语音推理基础设施 总览

> 一句话理解：**当输入从纯文本变成图像、视频和音频，推理基础设施的每个假设都要重写**——token 不再按字符计费、prefill 成本随分辨率爆炸、batch 里混进了第二个模型（视觉编码器），而语音场景下整条链路被压进 500ms 的延迟预算里运行，还必须支持「随时打断」。

## 学习目标

阅读完本主题后，你应该能够：

1. 说清视觉语言模型的三段式架构（vision encoder → projector → LLM），以及视觉 token 如何以「占位符 + embedding 替换」的方式进入统一的 token 序列。
2. 用动态分辨率公式估算任意图片的视觉 token 数，解释为什么一张手机照片能顶 6 倍文本 prompt 的 prefill 成本。
3. 拆解语音 Agent 的端到端延迟预算：VAD 端点检测、STT 定稿、LLM TTFT、TTS 首帧、网络传输各段各占多少，瓶颈在哪。
4. 理解双工（full-duplex）调度：打断（barge-in）检测、误触发恢复、按「用户实际听到的内容」截断对话历史。
5. 算清音频 codec token 账：帧率 × codebook 数 = tokens/秒，以及 1 分钟语音对 KV Cache 的压力是文本的多少倍。
6. 对比 vLLM / SGLang / TensorRT-LLM 的多模态支持现状，以及三段式（ASR→LLM→TTS）与端到端（GPT-4o Realtime / Gemini Live）两种语音架构的取舍。
7. 跑通并扩展本主题的 Mini Demo（视觉 token 调度、语音延迟预算、codec token 模拟、双工状态机）。
8. 回答多模态 serving 与实时语音基础设施相关的面试问题。

## 与 LLMOps 其他主题的关系

| 主题 | 解决的核心问题 | 与本主题的关系 |
|---|---|---|
| [vLLM](/04-llmops/vllm/) | 单引擎高吞吐 serving | vLLM 的 multimodal registry / input processor 是视觉 token 进入引擎的入口 |
| [SGLang](/04-llmops/sglang/) | LLM Program 与结构化生成 | SGLang 同时服务 LLM / 视觉语言 / 扩散模型，overlap 调度对多模态同样生效 |
| [TensorRT-LLM](/04-llmops/tensorrt-llm/) | NVIDIA 编译型推理引擎 | 编译期融合视觉塔与 LLM，多模态请求的 in-flight batching |
| [KV Cache 管理](/04-llmops/kv-cache/) | 注意力状态的复用与分层 | 视频与音频 token 让 KV 需求成倍膨胀，prefix 复用与逐出策略直接决定多模态并发上限 |
| [模型量化与压缩](/04-llmops/model-quantization/) | 权重与 KV 的位宽压缩 | 视觉塔与音频编码器的量化是降低多模态成本的第一杠杆 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 多引擎统一接入与治理 | 实时语音连接（WebRTC/WebSocket 长连接）的会话管理与路由 |
| [AI 集群网络](/02-cloud-native/ai-networking/) | 训练/推理集群网络 | WebRTC 边缘接入、SFU 级联与媒体面 QoS |
| [个人助理 Agent](/05-agent/personal-agent/) | 以人为中心的 Agent | 语音是个人 Agent 最自然的入口，实时打断体验由本主题的基建决定 |
| [RAG](/06-rag/) | 检索增强生成 | 多模态 RAG（图/音/视频检索）依赖本主题的视觉 encoder 服务与 embedding 链路 |

## 本章结构

1. [背景](01-background) — 模态爆炸：从「图生文」到 2026 年的语音 Agent 浪潮。
2. [核心思想](02-core-ideas) — 统一 token 序列、模态调度、流式与打断三大支柱。
3. [架构设计](03-architecture) — 语音 Agent 推理链路全景与三段式 vs 端到端之争。
4. [工作流程](04-runtime-workflow) — 一次实时语音对话的端到端时序。
5. [核心模块](05-core-modules) — vision encoder 服务、VAD、音频编解码、双工调度器。
6. [生态与源码分析](06-source-analysis) — vLLM / SGLang / TensorRT-LLM / 语音框架对比。
7. [Mini Demo](07-mini-demo) — 纯 Python 可运行的四类机制模拟。
8. [企业生产实践](08-production-practice) — 延迟预算管理、GPU 共享与成本核算。
9. [最佳实践](09-best-practices) — 分辨率治理、端点调优、误打断治理、容量规划。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 论文、官方文档与手册内回链。

## 一句话总结

多模态与语音推理基础设施回答的是同一个问题：**非文本的信息如何变成 token、如何被调度、如何在流式约束下按时返回**——它把推理引擎、媒体处理和实时通信三个领域缝在一起，是 2025-2026 年语音 Agent 爆发的地基。
