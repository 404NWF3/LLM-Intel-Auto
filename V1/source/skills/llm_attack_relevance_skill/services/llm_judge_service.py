"""LLM and rules-based judgement helpers."""

from __future__ import annotations

import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import SecretStr

from ..schemas.models import (
    EvidenceWindow,
    ItemJudgementResult,
    LLMAttackJudgementPayload,
    MatchedKeyword,
    SkillRuntimeOptions,
)

PROMPT_VERSION = "v1.0-article-judge"


class LLMAttackJudgeService:
    """Judge article-level relevance via LLM or explicit rules fallback."""

    PROMPT_VERSION = PROMPT_VERSION

    def __init__(
        self,
        *,
        model: str = "gpt-5-mini",
        temperature: float = 0.0,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.base_url = (
            base_url or os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
        )
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.prompt_text = self._load_prompt_text()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def judge(
        self,
        *,
        title: str | None,
        summary: str | None,
        matches: list[MatchedKeyword],
        evidence_windows: list[EvidenceWindow],
        runtime_options: SkillRuntimeOptions,
    ) -> tuple[LLMAttackJudgementPayload, bool, bool, str | None]:
        if runtime_options.judge_mode == "rules_only":
            return self._rules_only(matches, evidence_windows), False, False, None

        if not self.is_available():
            if runtime_options.judge_mode == "llm_required":
                raise RuntimeError("OPENAI_API_KEY is not configured for llm_required mode.")
            return (
                self._rules_only(matches, evidence_windows),
                False,
                True,
                "llm_unavailable_fallback_to_rules",
            )

        try:
            payload = self._judge_with_llm(
                title=title,
                summary=summary,
                matches=matches,
                evidence_windows=evidence_windows,
            )
            return payload, True, False, None
        except Exception as exc:  # pragma: no cover
            if runtime_options.judge_mode == "llm_required":
                raise RuntimeError(f"llm judgement failed: {exc}") from exc
            return (
                self._rules_only(matches, evidence_windows),
                False,
                True,
                "llm_call_failed_fallback_to_rules",
            )

    def _judge_with_llm(
        self,
        *,
        title: str | None,
        summary: str | None,
        matches: list[MatchedKeyword],
        evidence_windows: list[EvidenceWindow],
    ) -> LLMAttackJudgementPayload:
        from langchain_openai import ChatOpenAI

        included_windows = [window for window in evidence_windows if window.included_in_llm_prompt]
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt_text),
                (
                    "user",
                    (
                        "title: {title}\n"
                        "summary: {summary}\n"
                        "matched_keywords: {matched_keywords}\n"
                        "evidence_windows:\n{evidence_windows}\n"
                    ),
                ),
            ]
        )
        llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url,
            api_key=SecretStr(self.api_key) if self.api_key else None,
        )
        structured_llm = llm.with_structured_output(
            LLMAttackJudgementPayload,
            method="function_calling",
        )
        chain = prompt | structured_llm
        result = chain.invoke(
            {
                "title": title or "",
                "summary": summary or "",
                "matched_keywords": ", ".join(
                    f"{match.term}({match.term_type})@{match.sentence_index}" for match in matches[:50]
                ),
                "evidence_windows": "\n\n".join(
                    f"[{window.window_id}] {window.text}" for window in included_windows
                ),
            }
        )
        if isinstance(result, LLMAttackJudgementPayload):
            return result
        return LLMAttackJudgementPayload.model_validate(result)

    @staticmethod
    def _rules_only(
        matches: list[MatchedKeyword],
        evidence_windows: list[EvidenceWindow],
    ) -> LLMAttackJudgementPayload:
        llm_hits = sum(1 for match in matches if match.term_type == "llm_term")
        attack_hits = sum(1 for match in matches if match.term_type == "attack_term")
        exclusion_hits = sum(1 for match in matches if match.term_type == "exclusion_term")
        window_score = sum(window.score_hint or 0.0 for window in evidence_windows if window.included_in_llm_prompt)

        if llm_hits == 0 and attack_hits == 0:
            return LLMAttackJudgementPayload(
                judgement="irrelevant",
                confidence=0.98,
                scope_label="not_llm_attack",
                article_level_reason="No LLM-target terms or attack terms were found in the title, summary, or body windows.",
            )

        if exclusion_hits > 0 and attack_hits == 0:
            return LLMAttackJudgementPayload(
                judgement="irrelevant",
                confidence=0.9,
                scope_label="not_llm_attack",
                article_level_reason="The evidence is dominated by configured exclusion terms and lacks attack-specific support.",
            )

        if llm_hits > 0 and attack_hits > 0 and window_score >= 2.0:
            return LLMAttackJudgementPayload(
                judgement="relevant",
                confidence=min(0.95, 0.55 + (attack_hits * 0.06) + (llm_hits * 0.04)),
                scope_label="llm_attack",
                article_level_reason="The evidence windows jointly mention LLM-related targets and attack semantics, suggesting the article substantially discusses attacks on LLM systems.",
            )

        return LLMAttackJudgementPayload(
            judgement="uncertain",
            confidence=0.45,
            scope_label="uncertain_scope",
            article_level_reason="Some relevant signals were found, but the current windows are insufficient to safely conclude that the article is substantially about LLM attacks.",
        )

    @staticmethod
    def apply_payload_to_result(
        *,
        base_result: ItemJudgementResult,
        payload: LLMAttackJudgementPayload,
        llm_used: bool,
        degraded: bool,
        degraded_reason: str | None,
        model_name: str | None,
    ) -> ItemJudgementResult:
        route_action = {
            "relevant": "keep_and_parse",
            "irrelevant": "drop",
            "uncertain": "review",
        }[payload.judgement]
        base_result.judgement = payload.judgement
        base_result.route_action = route_action
        base_result.confidence = payload.confidence
        base_result.scope_label = payload.scope_label
        base_result.article_level_reason = payload.article_level_reason
        base_result.llm_used = llm_used
        base_result.degraded = degraded
        base_result.degraded_reason = degraded_reason
        base_result.llm_model_name = model_name if llm_used else None
        base_result.llm_prompt_version = PROMPT_VERSION
        return base_result

    @staticmethod
    def _load_prompt_text() -> str:
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "judge_article_llm_attack.md"
        return prompt_path.read_text(encoding="utf-8")
