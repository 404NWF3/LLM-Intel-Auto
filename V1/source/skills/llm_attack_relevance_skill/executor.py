"""Unified entrypoint for the LLM attack relevance skill."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .schemas.models import LLMAttackRelevanceRequest, LLMAttackRelevanceResult
from .services.orchestration_service import LLMAttackRelevanceOrchestrationService


class LLMAttackRelevanceSkill:
    """Coordinate the end-to-end article relevance judgement flow."""

    def __init__(self, *, llm_judge_service=None) -> None:
        self._orchestration_service = LLMAttackRelevanceOrchestrationService(
            llm_judge_service=llm_judge_service,
        )

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            validated_request = LLMAttackRelevanceRequest.model_validate(request)
        except ValidationError as exc:
            return LLMAttackRelevanceResult(
                run_id=str(request.get("run_id", "")),
                trace_id=request.get("trace_id"),
                status="failed",
                item_results=[],
                success_count=0,
                relevant_count=0,
                irrelevant_count=0,
                uncertain_count=0,
                failed_count=1,
                warnings=[str(exc)],
            ).model_dump(mode="python")

        return self._orchestration_service.run(validated_request).model_dump(mode="python")


def run_llm_attack_relevance_skill(
    request: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Stable function entrypoint used by intel agent workflows."""

    return LLMAttackRelevanceSkill(**kwargs).run(request)
