from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import langchain_openai


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

llm_client_factory = import_module(
    "agents.intel_agents.tools.llm_client_factory"
)


def test_dashscope_qwen3_structured_output_disables_thinking(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.delenv("OPENAI_ENABLE_THINKING", raising=False)
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)

    llm_client_factory.build_structured_chat_openai(
        model="qwen3.5-flash",
        temperature=0.0,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
    )

    assert captured["extra_body"] == {"enable_thinking": False}


def test_non_dashscope_model_keeps_default_request_shape(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.delenv("OPENAI_ENABLE_THINKING", raising=False)
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)

    llm_client_factory.build_structured_chat_openai(
        model="qwen-max",
        temperature=0.0,
        base_url="https://api.openai.com/v1",
        api_key="test-key",
    )

    assert captured["extra_body"] is None


def test_explicit_thinking_override_wins(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("OPENAI_ENABLE_THINKING", "true")
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)

    llm_client_factory.build_structured_chat_openai(
        model="qwen3.5-flash",
        temperature=0.0,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
    )

    assert captured["extra_body"] == {"enable_thinking": True}
