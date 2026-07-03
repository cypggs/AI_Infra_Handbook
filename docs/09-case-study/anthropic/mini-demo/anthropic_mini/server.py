"""Anthropic-style ``/v1/messages`` endpoint with prompt caching."""

from __future__ import annotations

import secrets

from fastapi import Body, FastAPI, Header, HTTPException

from anthropic_mini.cache import Block, PromptCache, estimate_tokens
from anthropic_mini.generator import complete, pick_model

app = FastAPI(title="Anthropic Mini Server", version="0.1.0")

# One shared prefix cache; workspace is supplied per request to model isolation.
cache = PromptCache()


def _system_to_blocks(system) -> list[Block]:
    blocks: list[Block] = []
    if isinstance(system, str):
        if system:
            blocks.append(Block("system", system))
    elif isinstance(system, list):
        for item in system:
            if isinstance(item, str):
                blocks.append(Block("system", item))
            elif isinstance(item, dict):
                blocks.append(
                    Block("system", item.get("text", ""), item.get("cache_control"))
                )
    return blocks


def _messages_to_blocks(messages: list) -> list[Block]:
    blocks: list[Block] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            blocks.append(Block("message", content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    blocks.append(
                        Block("message", part.get("text", ""), part.get("cache_control"))
                    )
                else:
                    blocks.append(Block("message", str(part)))
    return blocks


def _to_blocks(system, messages: list) -> list[Block]:
    # Cache prefix order: tools -> system -> messages (no tools in this demo).
    return _system_to_blocks(system) + _messages_to_blocks(messages)


def _apply_automatic_caching(blocks: list[Block], top_cc: dict) -> list[Block]:
    """Top-level ``cache_control`` marks the last cacheable block as a breakpoint."""
    if not blocks:
        return blocks
    ttl = top_cc.get("ttl", "5m")
    last = blocks[-1]
    if last.cache_control is None:
        blocks = blocks[:-1] + [last.with_cache_control({"type": "ephemeral", "ttl": ttl})]
    return blocks


def _breakpoints(blocks: list[Block]) -> list[int]:
    return [i for i, b in enumerate(blocks) if b.cache_control]


def _prompt(messages: list) -> str:
    return " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in messages
    )


@app.post("/v1/messages")
def create_message(body: dict = Body(...), x_api_key: str = Header(default="")):
    if x_api_key != "sk-demo":
        raise HTTPException(status_code=401, detail="invalid x-api-key")

    try:
        model = pick_model(body.get("model", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    system = body.get("system")
    messages = body.get("messages", []) or []
    top_cc = body.get("cache_control")
    workspace = body.get("workspace", "default")

    blocks = _to_blocks(system, messages)
    if top_cc:
        blocks = _apply_automatic_caching(blocks, top_cc)
    if not blocks:
        raise HTTPException(status_code=400, detail="prompt is empty")

    bps = _breakpoints(blocks) or [len(blocks) - 1]
    usage = cache.process(blocks, bps, workspace)

    text = complete(model, _prompt(messages))
    return {
        "id": f"msg_{secrets.token_hex(12)}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": usage.input_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens,
            "cache_creation": {
                "ephemeral_5m_input_tokens": usage.write_5m_tokens,
                "ephemeral_1h_input_tokens": usage.write_1h_tokens,
            },
            "output_tokens": estimate_tokens(text),
        },
    }


@app.get("/v1/cache/stats")
def cache_stats():
    """A small debug aid: how many entries the in-memory cache currently holds."""
    return {"entries": len(cache._entries)}
