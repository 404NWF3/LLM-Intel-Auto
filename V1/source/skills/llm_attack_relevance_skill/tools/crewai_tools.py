"""CrewAI adapter for the skill bundle."""

from __future__ import annotations

from ..executor import run_llm_attack_relevance_skill


class CrewAILLMAttackRelevanceTool:
    name = "llm_attack_relevance_tool"
    description = "Judge whether raw candidate content is substantially about attacks on LLM systems."

    def run(self, request: dict) -> dict:
        return run_llm_attack_relevance_skill(request)

    def __call__(self, request: dict) -> dict:
        return self.run(request)
