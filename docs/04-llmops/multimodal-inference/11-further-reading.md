# 11. 延伸阅读

> 一句话理解：多模态与语音推理横跨视觉模型、音频建模、实时系统三条文献线——以下按「论文 → 官方文档 → 手册内回链」组织，建议按 1→2→3 的顺序读。

## 11.1 论文与开源项目

**视觉与多模态架构**

- LLaVA（NeurIPS 2023）：Visual Instruction Tuning——projector 对齐范式的起点，"visual instruction tuning" 概念的奠基工作。
- Qwen2.5-VL 技术博客（2025）：原生动态分辨率 ViT、window attention、mRoPE 绝对时间编码——动态分辨率 token 预算的权威出处。
- Qwen3-VL（2025）：稀疏视频表示（每帧 token 较 Qwen2.5-VL 减半）、长视频理解——视频 token 治理的最新基线。

**音频与语音**

- Whisper（OpenAI, 2022）：Robust Speech Recognition via Large-Scale Weak Supervision——三段式 ASR 事实标准。
- SoundStream（2021）/ EnCodec（2022, Meta）：神经音频编解码与 RVQ token 化——codec token 的源头。
- SpeechTokenizer（2023）：统一语音 tokenization，语义/声学分层——「理解只用语义子集」的依据。
- Moshi / Mimi（Kyutai, 2024）：全双工语音到语音模型与 12.5Hz 低帧率 codec——开源端到端语音栈的参考实现。

**实时系统**

- LiveKit Agents 文档（docs.livekit.io/agents）：turn detection、自适应打断、误触发恢复的生产实践手册。
- Pipecat 文档（docs.pipecat.ai）：管道化 Agent 编排与 150+ 服务集成。

## 11.2 官方文档（版本现状以 2026-10 为准）

| 资源 | 覆盖 |
|---|---|
| vLLM Multimodal Inputs（docs.vllm.ai） | `multi_modal_data`、占位符、encoder 内容哈希缓存、`limit_mm_per_prompt`、视频解码后端与剪枝 |
| SGLang 文档（docs.sglang.io） | 统一 runtime 下的多模态/扩散模型支持 |
| OpenAI Realtime API 指南（developers.openai.com） | GA 接口：WebRTC/WebSocket、临时密钥、server VAD、打断参数 |
| Gemini Live API（ai.google.dev/gemini-api/docs/live） | WSS 双向流、16kHz 入/24kHz 出 PCM、内建打断、工具调用 |
| TensorRT-LLM Multimodal（nvidia.github.io/TensorRT-LLM） | 编译融合式 VLM 部署 |

## 11.3 手册内回链

| 主题 | 回链 | 关联点 |
|---|---|---|
| vLLM | [04-llmops/vllm](/04-llmops/vllm/) | 多模态注册表、input processor、encoder 缓存的实现宿主 |
| SGLang | [04-llmops/sglang](/04-llmops/sglang/) | 统一 runtime 与 overlap 调度对多模态请求的作用 |
| TensorRT-LLM | [04-llmops/tensorrt-llm](/04-llmops/tensorrt-llm/) | 编译期融合视觉塔的另一种范式 |
| Triton | [04-llmops/triton](/04-llmops/triton/) | 存量推理平台接入多模态引擎的部署形态 |
| KV Cache 管理 | [04-llmops/kv-cache](/04-llmops/kv-cache/) | 音频/视频 token 的 KV 压力、前缀复用与分层卸载 |
| 模型量化与压缩 | [04-llmops/model-quantization](/04-llmops/model-quantization/) | 视觉塔/ASR/TTS 模型量化的降本杠杆 |
| LLM Gateway | [04-llmops/llm-gateway](/04-llmops/llm-gateway/) | 长连接会话路由、媒体请求治理 |
| AI 集群网络 | [02-cloud-native/ai-networking](/02-cloud-native/ai-networking/) | WebRTC 边缘接入、媒体面带宽与 QoS |
| 端侧与边缘推理 | [04-llmops/edge-inference](/04-llmops/edge-inference/) | 端侧 VLM/ASR 推理、语音 codec 的功耗与内存预算、端云混合路由 |
| 个人助理 Agent | [05-agent/personal-agent](/05-agent/personal-agent/) | 语音作为个人 Agent 入口的交互形态 |
| RAG | [06-rag](/06-rag/) | 多模态检索（图/音/视频）与视觉 embedding 服务 |

## 11.4 拓展学习路线

1. 想深入视觉 token 经济学：先读 Qwen2.5-VL 博客的附录公式，再用本主题 Mini Demo 的场景 1/2 改参数做敏感性分析；
2. 想深入实时语音：把 OpenAI Realtime 的 server VAD 三个参数（threshold/silence_duration_ms/eagerness）映射到 Mini Demo 的 `VoiceConfig`，复现「更快的回合闭合 vs 更高误闭率」的权衡；
3. 想深入 codec：读 EnCodec 与 Mimi 两篇论文的量化部分，对照 `codec.py` 把「语义子集 KV」扩展练习做出来。

## 小结

三条线各挑一篇精读（LLaVA、Mimi、LiveKit turn detection），配上四个官方文档的当前接口，再加上手册内十个主题的回链——足够支撑从「会用多模态 API」到「能造多模态基础设施」的跨越。
