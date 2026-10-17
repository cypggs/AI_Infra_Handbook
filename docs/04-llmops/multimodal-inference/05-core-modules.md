# 5. 核心模块：vision encoder 服务、VAD、音频编解码、双工调度器

> 一句话理解：四个模块撑起多模态与语音推理的「非 LLM 半边天」——**vision encoder 服务负责把像素变成 token，VAD 负责给音频流切出语义边界，音频编解码负责把声波变成可建模的 token 序列，双工调度器负责让这一切在「随时打断」约束下有序发生**。

## 5.1 vision encoder 服务

视觉塔（ViT）把图片切成 patch 序列并映射到 LLM 的 embedding 空间，之后 projector（MLP 或 cross-attention）完成维度与空间对齐。

**动态分辨率**是现代视觉编码器的核心机制（Qwen2.5-VL 起成为标配）：

```text
输入图片任意分辨率
  → 像素总量钳制到 [min_pixels, max_pixels]（Qwen2.5-VL: 200704 ~ 1003520）
  → 边长对齐到 merge_size 的倍数（28 = 14 patch x 2 merge）
  → 视觉 token 数 = (W/28) x (H/28)，即 256 ~ 1280 tokens
```

| 输入 | 视觉 token 数 | 等效文本 prompt（200 token）倍数 |
|---|---|---|
| 224×224 缩略图 | 256（下限钳制） | 1.3x |
| 896×896 文档截图 | 1024 | 5.1x |
| 3024×4032 手机照片 | 1230 | 6.2x |
| 7680×4320 8K 图 | ~1222（上限钳制） | 6.1x |

（上表为 Mini Demo 场景 1 实测。）工程含义：**分辨率治理 = 成本治理**。一张不钳制的 8K 图会贡献近万 patch 的 encoder 计算；钳制后上限 1280 token。Qwen3-VL 进一步引入稀疏视频表示，把每帧 token 数再砍约一半。

**服务化要点**：

- 输入处理（下载、解码、缩放、RGBA 背景填充）与 encoder 前向解耦，前者是 I/O 密集、易被慢请求拖死，vLLM 对媒体下载设了默认超时（图 5s / 视频 30s / 音频 10s）；
- encoder 输出缓存以媒体内容哈希为 key（vLLM 默认开启），LLaVA 时代的「预处理 embedding」用法也以 `mm_embeds` 形式保留；
- 视频走独立解码后端（CPU: OpenCV/torchcodec；GPU: NVDEC/pynvvideocodec/deepstream），帧采样 FPS 是模型契约的一部分。

## 5.2 VAD 与端点检测

VAD（Voice Activity Detection）回答两个二元问题：**现在有没有人在说话**、**这句话说完了没有**。它是整条语音链路里被低估的瓶颈——端点检测的静音窗口直接决定响应延迟的下限。

三个层级的能力：

| 层级 | 机制 | 延迟 | 误触发 |
|---|---|---|---|
| 能量 VAD | 音量阈值 + 静音时长 | 极低 | 高（噪声敏感） |
| 神经 VAD | 小型帧级分类（silero 等） | 低 | 中 |
| 语义端点 | 在 VAD 之上用语言模型判断「话是否说完了」 | 中 | 低（理解犹豫、列举） |

OpenAI Realtime 的 server VAD 暴露 `threshold` / `silence_duration_ms` / `eagerness` 三个旋钮（LiveKit 文档示例：`threshold 0.7 + silence 400ms` 换更快的回合闭合）；Gemini Live 的端点在会话内配置。生产调优的一般规律：**静音窗口 200-400ms 是「抢话快」与「没说完就抢」之间的权衡点**。

VAD 的第二个职责是打断检测：播放中检测到语音能量 → 触发打断候选（见 5.4）。这里必须叠加「确认」逻辑，否则咳嗽与回通道会频繁误打断。

## 5.3 音频编解码：token 化的声波

端到端语音模型不说文本，说 codec token。神经音频编解码器（SoundStream → EnCodec → Mimi）把波形压成**残差向量量化（RVQ）token 流**：

```text
波形 24kHz ──▶ 编码器 ──▶ 每帧 N 个 codebook 的 token（帧率 12.5~75 Hz）
                             │
              语义子集（前 1-2 个 codebook）+ 声学细节（其余 codebook）
```

| codec | 帧率 | codebook 数 | 语义 codebook | tokens/秒 | 码率 | 帧延迟 |
|---|---|---|---|---|---|---|
| Mimi（Moshi 用） | 12.5 Hz | 8 | 前 2 | 100 | ~1.1 kbps | 80ms |
| EnCodec @6kbps | 75 Hz | 8 | — | 600 | 6 kbps | 13.3ms |
| EnCodec @1.5kbps | 75 Hz | 2 | — | 150 | 1.5 kbps | 13.3ms |

（Mini Demo 场景 4 实测，bits/token 由 codebook 大小 log2 得出。）这张表解释了端到端语音模型的两个关键工程性质：

1. **延迟 vs 保真**：低帧率 codec（Mimi 12.5Hz）每帧携带 80ms 音频，模型可以「低帧率思考」，首音与生成速度都受益，代价是声学细节少、更依赖大 codebook 表达能力；
2. **KV 压力**：Mimi 的 100 tokens/秒意味着 1 分钟对话上下文 = 6000 token——是同等文本（约 200 token/分钟）的 **30 倍**（EnCodec 75Hz 更夸张：180 倍）。语音模型必须配长上下文与激进 KV 管理（见 [KV Cache 管理](/04-llmops/kv-cache/)）。

语义/声学分层（SpeechTokenizer 的思想，Mimi 继承）还支撑了一个架构技巧：**理解只用语义子集**——把音频转成语义 token 喂给 LLM，再由声学部分负责还原声音，让「听懂」和「说好听」解耦。

## 5.4 双工调度器

双工调度器是会话的中枢状态机。其输入是事件流（VAD 触发、端点、ASR 定稿、LLM token、工具回调、播放进度），输出是对各下游服务的控制指令（取消、恢复、注入记忆、发起工具）。

核心数据结构是「按已播放截断的历史」：

```text
会话状态:
  transcript: [(speaker, text, audio_span)]   # 每段附带音频区间
  playback_cursor: 1350ms                      # 当前回答播放到这里
打断发生时:
  当前回答的 transcript 截断到 audio_span <= playback_cursor 的部分
  → LLM 下一轮请求只携带用户真正听到的内容
```

调度器的资源裁决（见 3.5）：打断取消与新响应的算力竞争，一般用「取消信号最高优先级 + 新请求插队但限速」处理；工具调用等待期注入 filler（"让我查一下……"）保住交互感。

## 5.5 模块间的时序契约

四个模块必须满足一组硬契约，否则端到端延迟失控：

| 契约 | 内容 | 违反后果 |
|---|---|---|
| 流式级联 | 每级输出粒度 ≤ 下一级可消费粒度 |  buffering 累积，首音超标 |
| 取消传播 | 取消指令到达任意下游 < 50ms | 打断后旧音频「幽灵播放」 |
| 历史一致性 | 截断只发生在已确认音频边界 | LLM 上下文与用户听到的不一致 |
| 背压 | 下游慢时上游可丢弃中间结果 | 内存膨胀、延迟抖动 |

## 小结

- vision encoder 服务的关键是动态分辨率钳制 + 内容哈希缓存 + 视频 GPU 解码；token 数（256-1280/张）决定 prefill 成本。
- VAD 决定延迟下限与打断灵敏度，现代系统用「神经 VAD + 语义端点」两级结构。
- 音频 codec 用帧率 × codebook 数定义 token 流；低帧率 codec 利于延迟，但音频上下文的 KV 压力是文本的数十倍。
- 双工调度器维护「按已播放截断的历史」，是打断正确性的最后防线。
