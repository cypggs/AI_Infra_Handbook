"""CPU-runnable mini demo of multimodal & speech inference infrastructure.

Modules:
- scheduler: multimodal request scheduling (visual token counting & mixed batching)
- voice:     end-to-end voice latency budget model (VAD/STT/LLM/TTS breakdown)
- codec:     audio codec token simulation (frame rate, bitrate, token counts)
- duplex:    full-duplex conversation state machine (barge-in, false interruption)
"""

__version__ = "0.1.0"
