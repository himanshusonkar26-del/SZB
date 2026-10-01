from __future__ import annotations

import json
from typing import Any

from groq import Groq

from himan.config import settings

_client: Groq | None = None


def client() -> Groq:
    global _client
    if not settings.groq_ready:
        raise RuntimeError("GROQ_API_KEY missing. Put it in .env")
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def chat_text(messages: list[dict[str, str]], temperature: float = 0.3) -> str:
    resp = client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def chat_json(messages: list[dict[str, str]]) -> dict[str, Any]:
    resp = client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM did not return a JSON object")
    return data
