from __future__ import annotations

import time
from typing import Any, Dict, List


def normalize_messages(messages: Any) -> List[Dict[str, str]]:
    """Ensure messages are a list of {role, content} dicts."""
    if not isinstance(messages, list):
        return []
    normalized: List[Dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, dict):
            normalized.append(
                {
                    "role": str(msg.get("role", "user")),
                    "content": str(msg.get("content", "")),
                }
            )
    return normalized


def openai_to_provider(provider_type: str, openai_request: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an OpenAI chat/completions request into a provider-specific mock request."""
    provider_request: Dict[str, Any] = {
        "provider_type": provider_type,
        "model": openai_request.get("model", ""),
        "messages": normalize_messages(openai_request.get("messages", [])),
        "temperature": openai_request.get("temperature", 0.7),
        "max_tokens": openai_request.get("max_tokens", 256),
        "stream": openai_request.get("stream", False),
    }

    if provider_type == "vllm":
        provider_request["vllm_specific"] = {
            "ignore_eos": False,
            "top_p": openai_request.get("top_p", 0.9),
        }
    elif provider_type == "triton":
        provider_request["triton_specific"] = {
            "protocol": "http",
            "timeout": 30,
        }

    return provider_request


def provider_to_openai(
    provider_name: str,
    request: Dict[str, Any],
    provider_response: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize a provider response to OpenAI chat.completion shape and annotate provider."""
    resp = dict(provider_response)
    resp.setdefault("id", f"chatcmpl-{int(time.time())}")
    resp.setdefault("object", "chat.completion")
    resp.setdefault("created", int(time.time()))
    resp.setdefault("model", request.get("model", "unknown"))
    if "choices" not in resp:
        resp["choices"] = [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            }
        ]
    if "usage" not in resp:
        resp["usage"] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    resp["provider"] = provider_name
    return resp
