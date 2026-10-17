# 7. 工程实践：Mini Demo

> 一句话理解：这个 Mini Demo 用纯 Python（CPU、无 GPU）模拟多模态与语音推理基础设施的四类核心机制——**视觉 token 调度、语音延迟预算、音频 codec token 账、双工会话状态机**，全部数字确定性可复现。

## 7.1 Demo 设计

真实系统的对应关系：

| Demo 模块 | 模拟对象 | 真实系统 |
|---|---|---|
| `multimodal_inference_mini/scheduler.py` | 动态分辨率视觉 token 计数；图文混合 batch 的双资源（encoder/LLM）调度与重叠 | vLLM `MultiModalProcessor` / SGLang 多模态 serving |
| `multimodal_inference_mini/voice.py` | first-audio 五段延迟预算；600ms SLO 余量分析；打断重响应成本 | OpenAI Realtime / LiveKit 延迟工程 |
| `multimodal_inference_mini/codec.py` | 音频 codec token 账：帧率 × codebook 数、码率、KV 增长倍数 | Mimi / EnCodec RVQ tokenizers |
| `multimodal_inference_mini/duplex.py` | 全双工状态机：打断确认、误触发恢复、按已播放截断历史 | LiveKit Agents turn 状态机 |

## 7.2 目录结构

```text
docs/04-llmops/multimodal-inference/mini-demo/
├── README.md
├── pyproject.toml          # numpy + pytest
├── conftest.py
├── multimodal_inference_mini/
│   ├── __init__.py
│   ├── scheduler.py        # visual_token_count / Request / MultimodalScheduler
│   ├── voice.py            # VoiceConfig / 延迟预算 / 打断成本
│   ├── codec.py            # CodecSpec / compare_codecs / streaming_chunk_plan
│   ├── duplex.py           # DuplexSession 状态机
│   └── demo.py             # 6 个端到端场景
└── tests/
    ├── test_scheduler.py   # 16 个用例
    ├── test_voice.py       # 12 个用例
    ├── test_codec.py       # 14 个用例
    ├── test_duplex.py      # 11 个用例
    └── test_demo.py        # 7 个用例
```

## 7.3 快速运行

```bash
cd docs/04-llmops/multimodal-inference/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m multimodal_inference_mini.demo
```

## 7.4 六个场景与实测输出

### 场景 1：分辨率 → 视觉 token → prefill 成本

Qwen2.5-VL 风格动态分辨率（像素钳制 200704~1003520，28×28 merge block）：

```text
224x224    ->   256 visual tokens | prefill    12.8 ms | =    1.3x text prompt(200)
448x448    ->   256 visual tokens | prefill    12.8 ms | =    1.3x text prompt(200)
896x896    ->  1024 visual tokens | prefill    51.2 ms | =    5.1x text prompt(200)
1568x1568  ->  1225 visual tokens | prefill    61.2 ms | =    6.1x text prompt(200)
3024x4032  ->  1230 visual tokens | prefill    61.5 ms | =    6.2x text prompt(200)
7680x4320  ->  1222 visual tokens | prefill    61.1 ms | =    6.1x text prompt(200)
```

读法：上下限钳制让 token 数有界（256~1280），但即便钳制后，一张手机照片仍相当于 6.2 倍文本 prompt 的 prefill 量——**「图越清越贵」的直觉被钳制住，但「有图就贵 5 倍起」是结构性的**。

### 场景 2：图文混合 batching 与 encoder 重叠

4 请求 × 200 文本 token，对照组无图、实验组每请求带 1 张 3024×4032 照片：

```text
text-only : llm_prefill    40.00 ms
mixed     : llm_prefill   286.00 ms (visual 4920 tokens, share 86.0%)
encoder   : 19680 patches, 307.5 ms (overlap 不阻塞)
makespan  : 307.5 ms | serial 593.5 ms
prefill slowdown: 7.15x
```

读法：混合 batch 的 prefill 成本放大 7.15 倍，其中 86% 的 token 来自图像；encoder 前向 307.5ms 与 LLM prefill 重叠后，makespan 取两者较大者（307.5ms）——若不重叠则串行 593.5ms。**encoder 独立池 + 流水线重叠几乎省下一半时间**。

### 场景 3：600ms 语音响应预算分解

默认配置的端到端 first-audio：

```text
endpointing        240.0 ms
stt_finalize       150.0 ms
llm_ttft           300.0 ms
tts_first_frame    120.0 ms
transport           40.0 ms
total              850.0 ms
budget 600 ms -> headroom -250.0 ms (meets=False)
```

距 600ms 预算差 250ms。把每段单独砍半的收益：

```text
endpointing         240 -> 120.0 ms | total 730.00 ms | gain 120.00 ms
stt_finalize        150 ->  75.0 ms | total 775.00 ms | gain  75.00 ms
llm_ttft            300 -> 150.0 ms | total 700.00 ms | gain 150.00 ms
tts_first_frame     120 ->  60.0 ms | total 790.00 ms | gain  60.00 ms
transport            40 ->  20.0 ms | total 830.00 ms | gain  20.00 ms
```

读法：杠杆排序为 LLM TTFT（150ms）> endpointing（120ms）> STT 定稿（75ms）——**优化要按杠杆排序做组合拳**：TTFT 靠级联小模型 + 前缀缓存，endpointing 靠语义端点模型，而不是平均用力。

### 场景 4：1 分钟语音的 codec token 账

```text
mimi           frames   750 | tokens  6000 | semantic 1500 |    1100 bps
encodec_6k     frames  4500 | tokens 36000 | semantic    0 |    6000 bps
encodec_1_5k   frames  4500 | tokens  9000 | semantic    0 |    1500 bps
KV 压力 mimi       : 1 分钟语音 = 30.0 倍文本 token 量(200/min)
KV 压力 encodec_6k : 1 分钟语音 = 180.0 倍文本 token 量(200/min)
KV 压力 encodec_1_5k : 1 分钟语音 = 45.0 倍文本 token 量(200/min)
```

读法：Mimi 用 1/6 的 token 数达到可用音质（低帧率 + 大 codebook），换来 KV 压力只有 EnCodec-6k 的 1/6——**codec 选择直接决定语音模型的上下文长度上限与单卡并发路数**。1500 个语义 token/分钟也支持「理解只用语义子集」的架构技巧。

### 场景 5：双工对话 trace（真打断 + 误触发）

```text
1200 ms  USER_SPEECH_END        LISTENING -> PROCESSING   | turn closed
1450 ms  RESPONSE_READY         PROCESSING -> SPEAKING    | playback started
2100 ms  USER_SPEECH_START      SPEAKING -> INTERRUPTED   | playback at 400/4000 ms
2200 ms  SPEECH_CONFIRMED       INTERRUPTED -> LISTENING  | history truncated to 400 ms of playback
3400 ms  USER_SPEECH_END        LISTENING -> PROCESSING   | turn closed
3650 ms  RESPONSE_READY         PROCESSING -> SPEAKING    | playback started
4300 ms  USER_SPEECH_START      SPEAKING -> INTERRUPTED   | playback at 500/2500 ms
4450 ms  SPEECH_FALSE_ALARM     INTERRUPTED -> SPEAKING   | resume playback
7000 ms  RESPONSE_DONE          SPEAKING -> LISTENING     | turn completed
interruptions=2 false_alarms=1 turns_completed=1
```

读法：第一次打断被确认——LLM 历史截断到用户实际听到的 400ms；第二次是咳嗽误触发——恢复播放且**不截断历史**（用户其实一直在听）。这正是 4.3 节误触发治理的状态机版本。

### 场景 6：打断后二次响应 vs 正常轮次

```text
正常轮次 first-audio :  850.00 ms
打断重响应           :  960.00 ms (vad 80.0 + cancel 30.0 + restart 850.0)
打断代价             :  110.00 ms
```

读法：打断的纯开销只有 110ms（VAD 触发 + 取消传播），二次响应主要重付整条管线的钱——这解释了为什么生产系统要在工具等待、长回答场景用预生成/缓存把「重启成本」摊薄。

## 7.5 可做的扩展练习

1. 给 `MultimodalScheduler` 加 chunked prefill：长视觉请求分块与文本请求交错，比较混合 batch 的最大等待时间；
2. 给 `DuplexSession` 加播放时钟：用 `advance_playback` 驱动 `SPEECH_CONFIRMED` 时的截断，验证「说完 4 秒被 0.4 秒打断」的文本截断公式；
3. 在 `voice.py` 里建模级联模型：endpointing 先由 5ms 级小模型触发、大模型 200ms 后精排取消，比较误闭合照率；
4. 给 `CodecSpec` 加「语义子集 KV」模式：LLM 只消费语义 codebook 的 token，对比 KV 占用与音质码率的权衡曲线；
5. 把 `streaming_chunk_plan` 接入 `DuplexSession`：模拟 TTS 按 80ms 块边合成边播，测量打断时「已合成未播放」的浪费量。
