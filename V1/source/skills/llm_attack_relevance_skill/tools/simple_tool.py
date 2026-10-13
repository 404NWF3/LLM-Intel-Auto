"""Simple direct-call tool adapter."""

from __future__ import annotations

from typing import Any

from ..executor import run_llm_attack_relevance_skill


class _LLMAttackRelevanceTool:
    name = "llm_attack_relevance_tool"
    description = "Filter raw candidate content for substantial LLM attack relevance."

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        return run_llm_attack_relevance_skill(request)


llm_attack_relevance_tool = _LLMAttackRelevanceTool()
