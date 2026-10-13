"""Pydantic contracts for the LLM attack relevance skill."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

JudgeMode = Literal["llm_required", "llm_optional", "rules_only"]
Judgement = Literal["relevant", "irrelevant", "uncertain"]
RouteAction = Literal["keep_and_parse", "drop", "review"]
ExecutionStatus = Literal["succeeded", "partial_success", "failed"]
TermType = Literal["llm_term", "attack_term", "exclusion_term"]


class RawCandidateItem(BaseModel):
    raw_id: str = Field(..., description="Raw record ID or temporary upstream ID")
    query_run_id: str | None = None
    source_name: str
    source_uri: str | None = None
    external_id: str | None = None
    title: str | None = None
    summary: str | None = None
    content: str
    published_at: str | None = None
    fetched_at: str | None = None
    raw_format: str | None = None
    language_code: str | None = None
    artifact_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_id", "source_name", "content")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("title", "summary")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class KeywordConfig(BaseModel):
    llm_terms: list[str] = Field(default_factory=list)
    attack_terms: list[str] = Field(default_factory=list)
    exclusion_terms: list[str] = Field(default_factory=list)
    window_sentences_before: int = Field(default=10, ge=0)
    window_sentences_after: int = Field(default=10, ge=0)


class SkillRuntimeOptions(BaseModel):
    judge_mode: JudgeMode = "llm_required"
    max_windows_per_item: int = Field(default=5, ge=1, le=20)
    merge_overlapping_windows: bool = True
    include_title_and_summary: bool = True
    include_global_head_tail_excerpt: bool = False
    max_sentences_per_window: int = Field(default=30, ge=1, le=80)
    max_total_chars_for_llm: int = Field(default=12000, ge=1000, le=50000)
    return_sentence_offsets: bool = True
    return_cleaned_text_excerpt: bool = False


class LLMAttackRelevanceRequest(BaseModel):
    run_id: str
    trace_id: str | None = None
    agent_name: str | None = "WP11RelevanceFilter"
    items: list[RawCandidateItem]
    keyword_config: KeywordConfig | None = None
    runtime_options: SkillRuntimeOptions = Field(default_factory=SkillRuntimeOptions)

    @field_validator("run_id")
    @classmethod
    def _strip_run_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("run_id must not be blank")
        return value

    @model_validator(mode="after")
    def _validate_items(self) -> "LLMAttackRelevanceRequest":
        if not self.items:
            raise ValueError("items must not be empty")
        return self


class MatchedKeyword(BaseModel):
    sentence_index: int
    term: str
    term_type: TermType
    char_start: int | None = None
    char_end: int | None = None


class EvidenceWindow(BaseModel):
    window_id: str
    start_sentence_index: int
    end_sentence_index: int
    matched_terms: list[MatchedKeyword] = Field(default_factory=list)
    text: str
    score_hint: float | None = None
    included_in_llm_prompt: bool = True


class ItemJudgementResult(BaseModel):
    raw_id: str
    query_run_id: str | None = None
    source_name: str
    source_uri: str | None = None
    judgement: Judgement
    route_action: RouteAction
    confidence: float = Field(..., ge=0.0, le=1.0)
    article_level_reason: str
    scope_label: Literal["llm_attack", "not_llm_attack", "uncertain_scope"] = "uncertain_scope"
    title_used: str | None = None
    summary_used: str | None = None
    total_sentences: int
    matched_keywords: list[MatchedKeyword] = Field(default_factory=list)
    evidence_windows: list[EvidenceWindow] = Field(default_factory=list)
    llm_model_name: str | None = None
    llm_prompt_version: str | None = None
    llm_used: bool = False
    degraded: bool = False
    degraded_reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LLMAttackRelevanceResult(BaseModel):
    run_id: str
    trace_id: str | None = None
    status: ExecutionStatus
    item_results: list[ItemJudgementResult]
    success_count: int
    relevant_count: int
    irrelevant_count: int
    uncertain_count: int
    failed_count: int
    warnings: list[str] = Field(default_factory=list)


class SentenceSpan(BaseModel):
    sentence_index: int
    text: str
    char_start: int | None = None
    char_end: int | None = None


class LLMAttackJudgementPayload(BaseModel):
    judgement: Judgement
    confidence: float = Field(..., ge=0.0, le=1.0)
    scope_label: Literal["llm_attack", "not_llm_attack", "uncertain_scope"]
    article_level_reason: str
