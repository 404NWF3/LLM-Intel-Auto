from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from backend.agents.saads_wp12.config import get_config


class LlmNotConfiguredError(RuntimeError):
    """Raised when LLM access is requested without valid configuration."""


def create_openai_client() -> OpenAI:
    config = get_config()
    if not config.openai_api_key:
        raise LlmNotConfiguredError("OPENAI_API_KEY is not configured.")
    client_kwargs: dict[str, Any] = {"api_key": config.openai_api_key}
    if config.openai_base_url:
        client_kwargs["base_url"] = config.openai_base_url
    return OpenAI(**client_kwargs)


def generate_json_response(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    config = get_config()
    client = create_openai_client()
    response = client.chat.completions.create(
        model=model or config.openai_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty content.")
    return json.loads(content)


def generate_text_response(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    config = get_config()
    client = create_openai_client()
    response = client.chat.completions.create(
        model=model or config.openai_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty content.")
    return content.strip()
