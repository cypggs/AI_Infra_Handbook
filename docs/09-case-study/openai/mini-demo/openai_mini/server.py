"""Minimal OpenAI-compatible chat completions server."""

from __future__ import annotations

import json
import secrets
import time

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from openai_mini.generator import complete, generate
from openai_mini.limiter import TokenBucket
from openai_mini.router import list_models, pick_model

app = FastAPI(title="OpenAI Mini Server", version="0.1.0")

# In-memory rate limiter: 10 requests/sec burst 20 per API key.
_buckets: dict[str, TokenBucket] = {}
BURST = 20.0
RATE = 10.0


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False
    max_tokens: int = 256
    temperature: float = 0.7


def _rate_limit(api_key: str) -> None:
    bucket = _buckets.setdefault(api_key, TokenBucket(rate=RATE, capacity=BURST))
    if not bucket.allow():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _extract_prompt(messages: list[Message]) -> str:
    # Concatenate user messages into a simple prompt for the mock generator.
    return " ".join(m.content for m in messages if m.role == "user")


def _stream_chunks(request_id: str, model: str, prompt: str):
    created = int(time.time())
    for i, token in enumerate(generate(model, prompt)):
        content = token if i == 0 else f" {token}"
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/v1/models")
def get_models():
    return {"object": "list", "data": list_models()}


@app.post("/v1/chat/completions")
def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    authorization: str = Header(default=""),
):
    # Validate API key.
    if authorization != "Bearer sk-demo":
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization.replace("Bearer ", "").strip() or "anonymous"
    _rate_limit(api_key)

    try:
        model = pick_model(body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    prompt = _extract_prompt(body.messages)
    request_id = f"chatcmpl-{secrets.token_hex(12)}"
    created = int(time.time())

    if body.stream:
        return StreamingResponse(
            _stream_chunks(request_id, model, prompt),
            media_type="text/event-stream",
        )

    text = complete(model, prompt)
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(text.split()),
            "total_tokens": len(prompt.split()) + len(text.split()),
        },
    }
