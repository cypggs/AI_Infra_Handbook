# Multimodal Inference Mini Demo

CPU-runnable, dependency-light simulation of the infrastructure layer behind
multimodal (image/video/audio) LLM serving and realtime voice agents.

It models four mechanisms that plain-text LLM serving never has to deal with:

| Module | Models | Real-world counterpart |
|---|---|---|
| `scheduler.py` | visual token counting (dynamic resolution) + mixed text/image batching with a separate encoder worker | vLLM / SGLang / TensorRT-LLM multimodal serving |
| `voice.py` | end-to-end voice response latency budget (endpointing / STT / LLM TTFT / TTS first frame / transport) and barge-in re-response cost | OpenAI Realtime / Gemini Live latency engineering |
| `codec.py` | audio codec token accounting (frame rate x codebooks -> tokens/s, bitrate, KV growth) | Mimi / EnCodec / SoundStream RVQ tokenizers |
| `duplex.py` | full-duplex conversation state machine (turn taking, confirmed interruption, false-alarm resume, history truncation) | LiveKit Agents / Pipecat turn-taking logic |

## Quick start

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m multimodal_inference_mini.demo
```

## Layout

```text
mini-demo/
├── pyproject.toml
├── conftest.py
├── README.md
├── multimodal_inference_mini/
│   ├── __init__.py
│   ├── scheduler.py   # visual_token_count, Request, MultimodalScheduler
│   ├── voice.py       # VoiceConfig, latency budget, interrupt cost
│   ├── codec.py       # CodecSpec, compare_codecs, streaming_chunk_plan
│   ├── duplex.py      # DuplexSession state machine
│   └── demo.py        # 6 end-to-end scenarios
└── tests/
    ├── test_scheduler.py  # 16 tests
    ├── test_voice.py      # 12 tests
    ├── test_codec.py      # 14 tests
    ├── test_duplex.py     # 11 tests
    └── test_demo.py       # 7 tests
```

All numbers are analytic and deterministic: identical runs produce identical
output.
