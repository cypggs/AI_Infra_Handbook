#!/usr/bin/env python3
"""Interactive demo for llm-gateway-mini.

Run with:
    cd docs/04-llmops/llm-gateway/mini-demo
    python -m llm_gateway_mini.demo
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from llm_gateway_mini.config import load_config
from llm_gateway_mini.server import GatewayApp, make_server

SAMPLE_CONFIG = """
providers:
  vllm-fast:
    name: vLLM-Fast
    type: vllm
    endpoint: http://localhost:8000
    weight: 3
    priority: 1
    latency_ms: 20
    failure_rate: 0.0
  triton-slow:
    name: Triton-Slow
    type: triton
    endpoint: http://localhost:8001
    weight: 1
    priority: 2
    latency_ms: 80
    failure_rate: 0.0
  openai-flaky:
    name: OpenAI-Flaky
    type: openai
    endpoint: http://localhost:8002
    weight: 2
    priority: 3
    latency_ms: 50
    failure_rate: 0.0
    failure_every_n: 3

models:
  gpt-mini:
    alias: gpt-mini
    providers: [openai-flaky, vllm-fast, triton-slow]
  llama-8b:
    alias: llama-8b
    providers: [vllm-fast, triton-slow]

rate_limits:
  default:
    requests_per_minute: 60
    burst: 10
"""


def run_demo() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    config = load_config(cfg_path)
    app = GatewayApp(config, router_strategy="round_robin")
    server = make_server(app, host="127.0.0.1", port=0)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        headers = {
            "Authorization": "Bearer sk-demo-123",
            "Content-Type": "application/json",
        }

        def send(idx: int):
            body = json.dumps(
                {
                    "model": "gpt-mini",
                    "messages": [{"role": "user", "content": f"hello {idx}"}],
                }
            ).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    provider = data.get("provider", "unknown")
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return provider, content[:60]
            except urllib.error.HTTPError as exc:
                return f"HTTP {exc.code}", exc.read().decode()[:60]

        results = []
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(send, i) for i in range(20)]
            for future in as_completed(futures):
                results.append(future.result())
        elapsed = time.perf_counter() - start

        print("\n=== Routing decisions ===")
        for provider, count in sorted(Counter(p for p, _ in results).items()):
            print(f"  {provider}: {count}")

        rate_limited = sum(1 for p, _ in results if p == "HTTP 429")
        print(f"\nRate-limited requests: {rate_limited}")

        print("\n=== Sample responses ===")
        for provider, content in results[:5]:
            print(f"  {provider}: {content}")

        print(f"\nCompleted in {elapsed:.3f}s")
        print("\n=== Metrics (Prometheus text) ===")
        print(app.handle_metrics())
    finally:
        server.shutdown()
        Path(cfg_path).unlink(missing_ok=True)


if __name__ == "__main__":
    run_demo()
