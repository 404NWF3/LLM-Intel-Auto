"""Tests for Phase 6 -- query telemetry and LLM-primary search reflection.

Covers:
    1. assess_collection_yield emits richer telemetry
    2. rules-only reflection remains backward compatible
    3. llm_required reflection with mocked LLM output
    4. llm_optional fallback on LLM failure
    5. reflection budget stop behavior
    6. audit DTO validation
    7. query feedback memory propagation
    8. reflect_search_strategy node rewrites collection plan
    9. runtime integration still closes loop once in stub mode
    10. state contains llm_reflection_audits
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

SearchReflectionAgent = import_module(
    "agents.intel_agents.agents.search_reflection_agent"
).SearchReflectionAgent
QueryTelemetryDTO = import_module("agents.intel_agents.schemas.query").QueryTelemetryDTO
CollectionYieldSummaryDTO = import_module(
    "agents.intel_agents.schemas.query"
).CollectionYieldSummaryDTO
LlmSearchReflectionAuditDTO = import_module(
    "agents.intel_agents.schemas.query"
).LlmSearchReflectionAuditDTO
QueryFeedbackRowDTO = import_module(
    "agents.intel_agents.schemas.query"
).QueryFeedbackRowDTO
RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO
CollectionPlanDTO = import_module("agents.intel_agents.schemas.plan").CollectionPlanDTO
SourceExecutionPlanDTO = import_module(
    "agents.intel_agents.schemas.plan"
).SourceExecutionPlanDTO
build_initial_state = import_module(
    "agents.intel_agents.orchestrator.state"
).build_initial_state
Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime
assess_collection_yield_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).assess_collection_yield_node
reflect_search_strategy_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).reflect_search_strategy_node


def _execution_stat(
    *,
    source_name: str = "github_advisories",
    query_run_id: str = "qrun-1",
    query_text: str = "langchain prompt injection",
    item_count: int = 3,
    success: bool = True,
) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "query_run_id": query_run_id,
        "query_text": query_text,
        "success": success,
        "item_count": item_count,
        "attempt_count": 1,
        "latency_ms": 120.0,
        "error_type": None,
        "error_message": None,
        "used_stub": True,
        "rate_limited": False,
        "degraded_from_live": False,
        "collector_role": "code_security_collector",
    }


def _raw_item(
    *,
    query_run_id: str = "qrun-1",
    source_name: str = "github_advisories",
    query_text: str = "langchain prompt injection",
) -> dict[str, Any]:
    return {
        "query_run_id": query_run_id,
        "source_name": source_name,
        "source_uri": f"stub://{source_name}/{query_run_id}",
        "external_id": query_run_id,
        "title": "Prompt injection advisory",
        "summary": "LangChain issue.",
        "author": None,
        "published_at": "2026-01-01T00:00:00+00:00",
        "fetched_at": "2026-01-01T00:00:01+00:00",
        "raw_format": "json",
        "artifact_ref": f"artifact://{query_run_id}",
        "payload_uri": f"artifact://{query_run_id}",
        "language_code": "en",
        "relevance_score": 0.9,
        "parser_status": "pending",
        "metadata": {
            "query_text": query_text,
            "query_intent": "broad_recall",
            "reflection_round": 0,
        },
        "content_hash": (query_run_id.replace("-", "a") + "a" * 64)[:64],
    }


def _plan() -> dict[str, Any]:
    return CollectionPlanDTO(
        run_mode="bootstrap",
        rationale="test plan",
        target_taxonomies=["OWASP-LLM-01"],
        source_plans=[
            SourceExecutionPlanDTO(
                source_name="github_advisories",
                source_type="code",
                priority=1.0,
                queries=["langchain prompt injection"],
                query_intent="broad_recall",
                query_provenance="test_seed",
                rewrite_reason=None,
                max_results=5,
                fetch_mode="bootstrap",
                time_window_days=7,
            )
        ],
        weak_signal_focus_terms=[],
        max_parallel_sources=1,
        max_items_per_source=5,
        max_reflection_rounds=1,
        reflection_enabled=True,
    ).model_dump(mode="python")


class FakeLlmReflector:
    PROMPT_VERSION = "v1.0-test"

    def __init__(
        self, result: dict[str, Any] | None = None, *, error: str | None = None
    ):
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def validate_connectivity(self) -> None:
        if self.error == "validate_failed":
            raise RuntimeError("validate_failed")

    def reflect(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.error and self.error != "validate_failed":
            raise RuntimeError(self.error)
        if self.result is None:
            raise AssertionError("No fake result configured")
        return self.result


def test_phase6_assess_collection_yield_emits_richer_telemetry() -> None:
    ctx = RuntimeContextDTO.default_stub().model_dump(mode="python")
    state = build_initial_state(runtime_context=ctx)
    state["collection_plan"] = _plan()
    state["source_execution_stats"] = [_execution_stat(item_count=3)]
    state["raw_items"] = [_raw_item(), _raw_item(query_run_id="qrun-1b")]

    result = assess_collection_yield_node(state)

    assert len(result["query_telemetry"]) == 1
    telemetry = QueryTelemetryDTO.model_validate(result["query_telemetry"][0])
    assert telemetry.source_type == "code"
    assert telemetry.query_provenance == "test_seed"
    assert telemetry.llm_reflection_hint is not None
    summary = CollectionYieldSummaryDTO.model_validate(
        result["collection_yield_summary"][0]
    )
    assert summary.reflection_evidence_summary is not None


def test_phase6_rules_only_reflection_rewrites_low_yield() -> None:
    agent = SearchReflectionAgent(strategy="rules_only")
    decision, audit, feedback = agent.reflect(
        [_execution_stat(item_count=0)],
        [
            QueryTelemetryDTO(
                query_run_id="qrun-1",
                source_name="github_advisories",
                source_type="code",
                query_text="langchain prompt injection",
                query_intent="broad_recall",
                query_provenance="test_seed",
                rewrite_round=0,
                rewrite_reason=None,
                result_count=0,
                parsed_count=0,
                duplicate_count=0,
                new_candidate_count=0,
                novelty_yield=0.0,
                noise_ratio=0.9,
                source_mismatch=False,
                llm_reflection_hint="Low recall signature.",
            ).model_dump(mode="python")
        ],
        {"reflection_round": 0, "max_reflection_rounds": 1},
    )

    assert decision["should_retry"] is True
    assert decision["rewritten_queries"]
    assert audit["strategy_executed"] == "rules_only"
    assert feedback


def test_phase6_llm_required_reflection_returns_structured_decision() -> None:
    fake_llm = FakeLlmReflector(
        {
            "should_retry": True,
            "stop_reason": "rewrite_generated",
            "diagnosis": "high_noise",
            "recommended_actions": ["narrow_query", "retry_once"],
            "rewritten_queries": [
                {
                    "source_name": "github_advisories",
                    "query_text": "langchain prompt injection exploit",
                    "query_intent": "precision_probe",
                    "rewrite_reason": "high_noise",
                    "rewrite_action": "narrower",
                    "expected_gain_dimension": "precision",
                    "parent_query_run_id": "qrun-1",
                    "parent_query_text": "langchain prompt injection",
                    "template_name": "gh_precision_probe",
                }
            ],
            "expected_gain_dimension": "precision",
            "confidence": 0.92,
            "evidence_summary": "High result volume but low novelty suggests narrowing.",
        }
    )
    agent = SearchReflectionAgent(
        strategy="llm_required",
        llm_reflector=fake_llm,
    )
    decision, audit, feedback = agent.reflect(
        [_execution_stat(item_count=8)],
        [
            QueryTelemetryDTO(
                query_run_id="qrun-1",
                source_name="github_advisories",
                source_type="code",
                query_text="langchain prompt injection",
                query_intent="broad_recall",
                query_provenance="test_seed",
                rewrite_round=0,
                rewrite_reason=None,
                result_count=8,
                parsed_count=8,
                duplicate_count=7,
                new_candidate_count=1,
                novelty_yield=0.125,
                noise_ratio=0.875,
                source_mismatch=False,
                llm_reflection_hint="High noise signature.",
            ).model_dump(mode="python")
        ],
        {"run_mode": "bootstrap", "reflection_round": 0, "max_reflection_rounds": 1},
        query_feedback_rows=[],
    )

    assert decision["should_retry"] is True
    assert decision["diagnosis"] == "high_noise"
    assert (
        decision["rewritten_queries"][0]["query_text"]
        == "langchain prompt injection exploit"
    )
    assert audit["strategy_executed"] == "llm_primary"
    assert len(feedback) == 1


def test_phase6_llm_optional_failure_falls_back_to_rules() -> None:
    agent = SearchReflectionAgent(
        strategy="llm_optional",
        llm_reflector=FakeLlmReflector(error="llm_failed"),
    )
    decision, audit, _ = agent.reflect(
        [_execution_stat(item_count=0)],
        [
            QueryTelemetryDTO(
                query_run_id="qrun-1",
                source_name="github_advisories",
                source_type="code",
                query_text="langchain prompt injection",
                query_intent="broad_recall",
                query_provenance="test_seed",
                rewrite_round=0,
                rewrite_reason=None,
                result_count=0,
                parsed_count=0,
                duplicate_count=0,
                new_candidate_count=0,
                novelty_yield=0.0,
                noise_ratio=0.8,
                source_mismatch=False,
                llm_reflection_hint="Low recall signature.",
            ).model_dump(mode="python")
        ],
        {"reflection_round": 0, "max_reflection_rounds": 1},
    )

    assert decision["should_retry"] is True
    assert audit["strategy_executed"] == "rules_only_degraded"
    assert audit["fallback_reason"] == "llm_failed"


def test_phase6_llm_required_failure_raises() -> None:
    agent = SearchReflectionAgent(
        strategy="llm_required",
        llm_reflector=FakeLlmReflector(error="llm_failed"),
    )
    with pytest.raises(RuntimeError, match="LLM search reflection required but failed"):
        agent.reflect([], [], {"reflection_round": 0, "max_reflection_rounds": 1})


def test_phase6_budget_stop_short_circuits_reflection() -> None:
    agent = SearchReflectionAgent(strategy="llm_required")
    decision, audit, feedback = agent.reflect(
        [],
        [],
        {"reflection_round": 1, "max_reflection_rounds": 1},
    )

    assert decision["should_retry"] is False
    assert decision["stop_reason"] == "reflection_budget_exhausted"
    assert audit["strategy_executed"] == "budget_stop"
    assert feedback == []


def test_phase6_audit_dto_validates() -> None:
    audit = LlmSearchReflectionAuditDTO.model_validate(
        {
            "reflection_round": 0,
            "strategy_requested": "llm_required",
            "strategy_executed": "llm_primary",
            "llm_model": "qwen-max",
            "prompt_version": "v1.0-test",
            "should_retry": True,
            "stop_reason": "rewrite_generated",
            "diagnosis": "high_noise",
            "expected_gain_dimension": "precision",
            "confidence": 0.91,
            "rewritten_query_count": 1,
            "rewritten_sources": ["github_advisories"],
            "evidence_summary": "High noise.",
            "fallback_reason": None,
            "invoked_at": "2026-03-16T00:00:00+00:00",
        }
    )
    assert audit.strategy_executed == "llm_primary"


def test_phase6_reflect_search_strategy_node_rewrites_collection_plan() -> None:
    ctx = RuntimeContextDTO.default_stub().model_dump(mode="python")
    ctx["reflection_strategy"] = "llm_optional"
    state = build_initial_state(runtime_context=ctx)
    state["collection_plan"] = _plan()
    state["collection_coordination"] = {
        "engine": "fallback",
        "assignments": [
            {
                "source_name": "github_advisories",
                "collector_role": "CodeSecurityCollector",
            }
        ],
        "collector_agents": [],
        "summary": "stale coordination",
    }
    state["query_telemetry"] = [
        QueryTelemetryDTO(
            query_run_id="qrun-1",
            source_name="github_advisories",
            source_type="code",
            query_text="langchain prompt injection",
            query_intent="broad_recall",
            query_provenance="test_seed",
            rewrite_round=0,
            rewrite_reason=None,
            result_count=0,
            parsed_count=0,
            duplicate_count=0,
            new_candidate_count=0,
            novelty_yield=0.0,
            noise_ratio=0.9,
            source_mismatch=False,
            llm_reflection_hint="Low recall signature.",
        ).model_dump(mode="python")
    ]
    state["source_execution_stats"] = [_execution_stat(item_count=0)]

    result = reflect_search_strategy_node(state)

    assert result["reflection_needed"] is True
    assert result["reflection_round"] == 1
    assert result["llm_reflection_audits"]
    assert result["collection_plan"]["source_plans"][0]["rewrite_reason"] in {
        "low_yield",
        "high_noise",
        "source_mismatch",
    }
    assert (
        result["collection_plan"]["source_plans"][0]["query_provenance"]
        == "phase6_reflection_rewrite"
    )
    assert result["runtime_context"]["query_feedback_rows"]
    QueryFeedbackRowDTO.model_validate(
        result["runtime_context"]["query_feedback_rows"][0]
    )


def test_phase6_feedback_rows_keep_per_source_diagnoses() -> None:
    agent = SearchReflectionAgent(strategy="rules_only")
    decision, _, feedback = agent.reflect(
        [
            _execution_stat(
                source_name="github_advisories", query_run_id="qrun-1", item_count=8
            )
        ],
        [
            QueryTelemetryDTO(
                query_run_id="qrun-1",
                source_name="github_advisories",
                source_type="code",
                query_text="langchain prompt injection",
                query_intent="broad_recall",
                query_provenance="test_seed",
                rewrite_round=0,
                rewrite_reason=None,
                result_count=8,
                parsed_count=8,
                duplicate_count=7,
                new_candidate_count=1,
                novelty_yield=0.125,
                noise_ratio=0.875,
                source_mismatch=False,
                llm_reflection_hint="High noise signature.",
            ).model_dump(mode="python"),
            QueryTelemetryDTO(
                query_run_id="qrun-2",
                source_name="arxiv",
                source_type="paper",
                query_text="prompt injection language model",
                query_intent="evidence_corroboration",
                query_provenance="test_seed",
                rewrite_round=0,
                rewrite_reason=None,
                result_count=0,
                parsed_count=0,
                duplicate_count=0,
                new_candidate_count=0,
                novelty_yield=0.0,
                noise_ratio=0.0,
                source_mismatch=False,
                llm_reflection_hint="Low recall signature.",
            ).model_dump(mode="python"),
        ],
        {"reflection_round": 0, "max_reflection_rounds": 1},
    )

    assert decision["should_retry"] is True
    feedback_by_query = {row["query_run_id"]: row for row in feedback}
    assert feedback_by_query["qrun-1"]["reflection_diagnosis"] == "high_noise"
    assert feedback_by_query["qrun-1"]["expected_gain_dimension"] == "precision"
    assert feedback_by_query["qrun-2"]["reflection_diagnosis"] == "low_recall"
    assert feedback_by_query["qrun-2"]["expected_gain_dimension"] == "recall"


def test_phase6_runtime_stub_reflection_loop_still_rewrites_once() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run(force_low_yield=True)

    assert result["run_status"] == "succeeded"
    assert result["reflection_round"] == 1
    assert result["llm_reflection_audits"]
    assert result["collection_plan"]["source_plans"][0]["rewrite_reason"] in {
        "low_yield",
        "high_noise",
    }


def test_phase6_runtime_state_contains_llm_reflection_audits() -> None:
    state = build_initial_state()
    assert "llm_reflection_audits" in state
    assert state["llm_reflection_audits"] == []


def test_phase6_store_raw_records_only_ingests_latest_query_runs() -> None:
    ctx = RuntimeContextDTO.default_stub().model_dump(mode="python")
    state = build_initial_state(runtime_context=ctx)
    state["raw_items"] = [
        _raw_item(query_run_id="qrun-1"),
        _raw_item(query_run_id="qrun-2"),
    ]
    state["processed_subject_ids"] = ["qrun-1"]

    store_raw_records_node = import_module(
        "agents.intel_agents.orchestrator.nodes"
    ).store_raw_records_node
    result = store_raw_records_node(state)

    assert len(result["stored_raw_records"]) == 1
    assert result["stored_raw_records"][0]["query_run_id"] == "qrun-2"
    assert result["runtime_context"]["latest_ingested_query_run_ids"] == ["qrun-2"]


def test_phase6_assess_collection_yield_only_uses_latest_query_runs() -> None:
    ctx = RuntimeContextDTO.default_stub().model_dump(mode="python")
    ctx["latest_ingested_query_run_ids"] = ["qrun-2"]
    state = build_initial_state(runtime_context=ctx)
    state["collection_plan"] = CollectionPlanDTO(
        run_mode="bootstrap",
        rationale="test plan",
        target_taxonomies=["OWASP-LLM-01"],
        source_plans=[
            SourceExecutionPlanDTO(
                source_name="github_advisories",
                source_type="code",
                priority=1.0,
                queries=["langchain prompt injection"],
                query_intent="broad_recall",
                query_provenance="test_seed",
                rewrite_reason=None,
                max_results=5,
                fetch_mode="bootstrap",
                time_window_days=7,
            ),
            SourceExecutionPlanDTO(
                source_name="arxiv",
                source_type="paper",
                priority=0.9,
                queries=["prompt injection language model"],
                query_intent="evidence_corroboration",
                query_provenance="test_seed",
                rewrite_reason=None,
                max_results=5,
                fetch_mode="bootstrap",
                time_window_days=30,
            ),
        ],
        weak_signal_focus_terms=[],
        max_parallel_sources=2,
        max_items_per_source=5,
        max_reflection_rounds=1,
        reflection_enabled=True,
    ).model_dump(mode="python")
    state["source_execution_stats"] = [
        _execution_stat(
            source_name="github_advisories",
            query_run_id="qrun-1",
            item_count=9,
        ),
        _execution_stat(
            source_name="arxiv",
            query_run_id="qrun-2",
            query_text="prompt injection language model",
            item_count=1,
        ),
    ]
    state["raw_items"] = [
        _raw_item(query_run_id="qrun-1", source_name="github_advisories"),
        _raw_item(
            query_run_id="qrun-2",
            source_name="arxiv",
            query_text="prompt injection language model",
        ),
    ]

    result = assess_collection_yield_node(state)

    assert len(result["query_telemetry"]) == 1
    telemetry = QueryTelemetryDTO.model_validate(result["query_telemetry"][0])
    assert telemetry.query_run_id == "qrun-2"


def test_phase6_assess_collection_yield_can_naturally_reach_high_noise() -> None:
    ctx = RuntimeContextDTO.default_stub().model_dump(mode="python")
    ctx["latest_ingested_query_run_ids"] = ["qrun-noise-1"]
    state = build_initial_state(runtime_context=ctx)
    state["collection_plan"] = CollectionPlanDTO(
        run_mode="bootstrap",
        rationale="noise test plan",
        target_taxonomies=["OWASP-LLM-01"],
        source_plans=[
            SourceExecutionPlanDTO(
                source_name="reddit",
                source_type="community",
                priority=1.0,
                queries=["llm jailbreak"],
                query_intent="weak_signal_probe",
                query_provenance="test_seed",
                rewrite_reason=None,
                max_results=5,
                fetch_mode="weak_signal",
                time_window_days=7,
            )
        ],
        weak_signal_focus_terms=[],
        max_parallel_sources=1,
        max_items_per_source=5,
        max_reflection_rounds=1,
        reflection_enabled=True,
    ).model_dump(mode="python")
    state["source_execution_stats"] = [
        _execution_stat(
            source_name="reddit",
            query_run_id="qrun-noise-1",
            query_text="llm jailbreak",
            item_count=3,
        )
    ]
    noisy_item = _raw_item(
        query_run_id="qrun-noise-1",
        source_name="reddit",
        query_text="llm jailbreak",
    )
    noisy_item["summary"] = "short"
    noisy_item["relevance_score"] = 0.45
    noisy_item["metadata"] = {
        **noisy_item["metadata"],
        "execution_profile": "weak_signal_scan",
    }
    state["raw_items"] = [noisy_item, dict(noisy_item), dict(noisy_item)]

    result = assess_collection_yield_node(state)

    telemetry = QueryTelemetryDTO.model_validate(result["query_telemetry"][0])
    summary = CollectionYieldSummaryDTO.model_validate(
        result["collection_yield_summary"][0]
    )
    assert telemetry.noise_ratio > 0.6
    assert summary.high_noise is True
