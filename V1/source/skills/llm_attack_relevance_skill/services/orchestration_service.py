"""Top-level orchestration for the skill bundle."""

from __future__ import annotations

import json
from pathlib import Path

from ..schemas.models import ItemJudgementResult, KeywordConfig, LLMAttackRelevanceRequest, LLMAttackRelevanceResult
from .cleaning_service import CleaningService
from .keyword_locator_service import KeywordLocatorService
from .llm_judge_service import LLMAttackJudgeService
from .sentence_service import SentenceService
from .window_builder_service import WindowBuilderService


class LLMAttackRelevanceOrchestrationService:
    """Coordinate cleaning, sentence splitting, windowing, and judgement."""

    def __init__(self, *, llm_judge_service=None) -> None:
        self._cleaning_service = CleaningService()
        self._sentence_service = SentenceService()
        self._keyword_locator_service = KeywordLocatorService()
        self._window_builder_service = WindowBuilderService()
        self._llm_judge_service = llm_judge_service or LLMAttackJudgeService()

    def run(self, request: LLMAttackRelevanceRequest) -> LLMAttackRelevanceResult:
        keyword_config = request.keyword_config or self._load_default_keyword_config()
        warnings: list[str] = []
        item_results: list[ItemJudgementResult] = []
        failed_count = 0

        for item in request.items:
            cleaned_content = self._cleaning_service.clean_text(item.content)
            if not cleaned_content:
                failed_count += 1
                item_results.append(
                    ItemJudgementResult(
                        raw_id=item.raw_id,
                        query_run_id=item.query_run_id,
                        source_name=item.source_name,
                        source_uri=item.source_uri,
                        judgement="uncertain",
                        route_action="review",
                        confidence=0.0,
                        article_level_reason="The candidate item did not contain usable content after cleaning.",
                        title_used=item.title,
                        summary_used=item.summary,
                        total_sentences=0,
                        notes=[],
                        errors=["content_empty_after_cleaning"],
                    )
                )
                continue

            sentences = self._sentence_service.split_sentences(cleaned_content)
            matches = self._keyword_locator_service.locate(
                sentences=sentences,
                keyword_config=keyword_config,
                title=item.title,
                summary=item.summary,
            )
            evidence_windows, notes = self._window_builder_service.build_windows(
                sentences=sentences,
                matches=matches,
                keyword_config=keyword_config,
                runtime_options=request.runtime_options,
            )
            base_result = ItemJudgementResult(
                raw_id=item.raw_id,
                query_run_id=item.query_run_id,
                source_name=item.source_name,
                source_uri=item.source_uri,
                judgement="uncertain",
                route_action="review",
                confidence=0.0,
                article_level_reason="Pending judgement.",
                title_used=item.title if request.runtime_options.include_title_and_summary else None,
                summary_used=item.summary if request.runtime_options.include_title_and_summary else None,
                total_sentences=len(sentences),
                matched_keywords=matches,
                evidence_windows=evidence_windows,
                notes=notes,
                errors=[],
            )

            if not matches:
                base_result.judgement = "irrelevant"
                base_result.route_action = "drop"
                base_result.confidence = 0.98
                base_result.scope_label = "not_llm_attack"
                base_result.article_level_reason = "No configured LLM or attack terms were found, so no evidence windows could be built."
                base_result.llm_prompt_version = self._llm_judge_service.PROMPT_VERSION
                item_results.append(base_result)
                continue

            try:
                payload, llm_used, degraded, degraded_reason = self._llm_judge_service.judge(
                    title=item.title if request.runtime_options.include_title_and_summary else None,
                    summary=item.summary if request.runtime_options.include_title_and_summary else None,
                    matches=matches,
                    evidence_windows=evidence_windows,
                    runtime_options=request.runtime_options,
                )
                result = self._llm_judge_service.apply_payload_to_result(
                    base_result=base_result,
                    payload=payload,
                    llm_used=llm_used,
                    degraded=degraded,
                    degraded_reason=degraded_reason,
                    model_name=self._llm_judge_service.model,
                )
            except Exception as exc:
                failed_count += 1
                base_result.errors.append(str(exc))
                base_result.judgement = "uncertain"
                base_result.route_action = "review"
                base_result.confidence = 0.0
                base_result.scope_label = "uncertain_scope"
                base_result.article_level_reason = "The item could not complete article-level judgement due to an execution error."
                base_result.degraded = True
                base_result.degraded_reason = "judgement_execution_failed"
                base_result.llm_prompt_version = self._llm_judge_service.PROMPT_VERSION
                result = base_result
            item_results.append(result)

        relevant_count = sum(1 for item in item_results if item.judgement == "relevant")
        irrelevant_count = sum(1 for item in item_results if item.judgement == "irrelevant")
        uncertain_count = sum(1 for item in item_results if item.judgement == "uncertain")
        success_count = len(item_results) - failed_count
        status = self._derive_status(item_results=item_results, failed_count=failed_count)
        return LLMAttackRelevanceResult(
            run_id=request.run_id,
            trace_id=request.trace_id,
            status=status,
            item_results=item_results,
            success_count=success_count,
            relevant_count=relevant_count,
            irrelevant_count=irrelevant_count,
            uncertain_count=uncertain_count,
            failed_count=failed_count,
            warnings=warnings,
        )

    @staticmethod
    def _derive_status(
        *,
        item_results: list[ItemJudgementResult],
        failed_count: int,
    ) -> str:
        if not item_results:
            return "failed"
        if failed_count == len(item_results):
            return "failed"
        if failed_count > 0:
            return "partial_success"
        return "succeeded"

    @staticmethod
    def _load_default_keyword_config() -> KeywordConfig:
        config_path = Path(__file__).resolve().parent.parent / "config" / "keyword_config.yaml"
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return KeywordConfig.model_validate(payload)
