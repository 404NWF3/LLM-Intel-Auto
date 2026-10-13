"""Tests for LLM-aware SupervisorAgent and its linkage with Phase 6 feedback."""

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

SupervisorAgent = import_module(
    "agents.intel_agents.agents.supervisor_agent"
).SupervisorAgent
RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO
LlmPlanningAuditDTO = import_module(
    "agents.intel_agents.schemas.query"
).LlmPlanningAuditDTO
QueryFeedbackRowDTO = import_module(
    "agents.intel_agents.schemas.query"
).QueryFeedbackRowDTO
supervisor_plan_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).supervisor_plan_node
build_initial_state = import_module(
    "agents.intel_agents.orchestrator.state"
).build_initial_state
Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime


class FakePlanner:
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

    def plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.error and self.error != "validate_failed":
            raise RuntimeError(self.error)
        if self.result is None:
            raise AssertionError("No fake plan configured")
        return self.result


def _runtime_context() -> dict[str, Any]:
    return RuntimeContextDTO.default_stub().model_dump(mode="python")


def _feedback_row(
    *,
    source_name: str = "github_advisories",
    diagnosis: str = "high_noise",
    query_text: str = "langchain prompt injection",
) -> dict[str, Any]:
    return QueryFeedbackRowDTO(
        query_run_id="qrun-1",
        source_name=source_name,
        query_text=query_text,
        query_intent="broad_recall",
        rewrite_round=0,
        result_count=8,
        parsed_count=8,
        duplicate_count=7,
        novelty_yield=0.125,
        noise_ratio=0.875,
        source_mismatch=False,
        reflection_diagnosis=diagnosis,
        reflection_action="narrower",
        should_retry=True,
        expected_gain_dimension="precision",
        llm_confidence=0.92,
    ).model_dump(mode="python")


def test_phase6_supervisor_rules_only_produces_valid_plan() -> None:
    ctx = _runtime_context()
    agent = SupervisorAgent(strategy="rules_only")

    plan, audit = agent.plan_run(
        ctx,
        ctx["coverage_snapshot"],
        ctx["source_quality_rows"],
        query_feedback_rows=[],
        weak_signal_summary=[],
    )

    assert plan["source_plans"]
    assert audit["strategy_executed"] == "rules_only"
    assert audit["source_plan_count"] == len(plan["source_plans"])


def test_phase6_supervisor_llm_required_uses_feedback_memory() -> None:
    ctx = _runtime_context()
    fake = FakePlanner(
        {
            "rationale": "Historical feedback shows GitHub queries need precision and papers need corroboration.",
            "target_taxonomies": ["OWASP-LLM-01", "OWASP-LLM-07"],
            "source_plans": [
                {
                    "source_name": "github_advisories",
                    "query_text": "langchain prompt injection exploit",
                    "query_intent": "precision_probe",
                    "query_provenance": "llm_supervisor_plan",
                    "rewrite_reason": "feedback_high_noise",
                    "priority": 0.95,
                    "max_results": 8,
                    "time_window_days": 14,
                    "fetch_mode": "bootstrap",
                },
                {
                    "source_name": "arxiv",
                    "query_text": "prompt injection evidence language model",
                    "query_intent": "evidence_corroboration",
                    "query_provenance": "llm_supervisor_plan",
                    "rewrite_reason": None,
                    "priority": 0.8,
                    "max_results": 6,
                    "time_window_days": 30,
                    "fetch_mode": "bootstrap",
                },
            ],
            "weak_signal_focus_terms": ["jailbreak", "agent exploit"],
            "max_parallel_sources": 2,
            "max_items_per_source": 8,
            "max_reflection_rounds": 1,
            "reflection_enabled": True,
            "confidence": 0.93,
        }
    )
    agent = SupervisorAgent(strategy="llm_required", planner=fake)

    plan, audit = agent.plan_run(
        ctx,
        ctx["coverage_snapshot"],
        ctx["source_quality_rows"],
        query_feedback_rows=[_feedback_row()],
        weak_signal_summary=[],
    )

    assert fake.calls
    assert fake.calls[0]["query_feedback_rows"]
    assert plan["source_plans"][0]["query_intent"] == "precision_probe"
    assert audit["strategy_executed"] == "llm_primary"
    assert audit["feedback_rows_used"] == 1


def test_phase6_supervisor_llm_optional_falls_back_to_rules() -> None:
    ctx = _runtime_context()
    agent = SupervisorAgent(
        strategy="llm_optional",
        planner=FakePlanner(error="planner_failed"),
    )

    plan, audit = agent.plan_run(
        ctx,
        ctx["coverage_snapshot"],
        ctx["source_quality_rows"],
        query_feedback_rows=[_feedback_row()],
        weak_signal_summary=[],
    )

    assert plan["source_plans"]
    assert audit["strategy_executed"] == "rules_only_degraded"
    assert audit["fallback_reason"] == "planner_failed"


def test_phase6_supervisor_invalid_llm_plan_marks_degraded_audit() -> None:
    ctx = _runtime_context()
    agent = SupervisorAgent(
        strategy="llm_optional",
        planner=FakePlanner(
            {
                "rationale": "invalid plan with unknown source",
                "target_taxonomies": ["OWASP-LLM-01"],
                "source_plans": [
                    {
                        "source_name": "unknown_source",
                        "query_text": "bad query",
                        "query_intent": "broad_recall",
                        "query_provenance": "llm_supervisor_plan",
                        "rewrite_reason": None,
                        "priority": 0.8,
                        "max_results": 5,
                        "time_window_days": 7,
                        "fetch_mode": "bootstrap",
                    }
                ],
                "weak_signal_focus_terms": [],
                "max_parallel_sources": 1,
                "max_items_per_source": 5,
                "max_reflection_rounds": 1,
                "reflection_enabled": True,
                "confidence": 0.91,
            }
        ),
    )

    plan, audit = agent.plan_run(
        ctx,
        ctx["coverage_snapshot"],
        ctx["source_quality_rows"],
        query_feedback_rows=[],
        weak_signal_summary=[],
    )

    assert plan["source_plans"]
    assert audit["strategy_executed"] == "rules_only_degraded"
    assert audit["fallback_reason"] == "llm_plan_filtered_out"


def test_phase6_supervisor_llm_required_failure_raises() -> None:
    ctx = _runtime_context()
    agent = SupervisorAgent(
        strategy="llm_required",
        planner=FakePlanner(error="planner_failed"),
    )

    with pytest.raises(
        RuntimeError, match="LLM supervisor planning required but failed"
    ):
        agent.plan_run(
            ctx,
            ctx["coverage_snapshot"],
            ctx["source_quality_rows"],
            query_feedback_rows=[],
            weak_signal_summary=[],
        )


def test_phase6_supervisor_plan_node_emits_planning_audit() -> None:
    ctx = _runtime_context()
    ctx["planning_strategy"] = "rules_only"
    state = build_initial_state(runtime_context=ctx)

    result = supervisor_plan_node(state)

    assert result["collection_plan"] is not None
    assert result["llm_planning_audits"]
    LlmPlanningAuditDTO.model_validate(result["llm_planning_audits"][0])


def test_phase6_feedback_influences_next_rules_plan() -> None:
    ctx = _runtime_context()
    agent = SupervisorAgent(strategy="rules_only")

    plan, _ = agent.plan_run(
        ctx,
        ctx["coverage_snapshot"],
        ctx["source_quality_rows"],
        query_feedback_rows=[_feedback_row()],
        weak_signal_summary=[],
    )

    github_plan = next(
        row for row in plan["source_plans"] if row["source_name"] == "github_advisories"
    )
    assert github_plan["query_intent"] == "precision_probe"
    assert github_plan["rewrite_reason"] == "feedback_high_noise"


def test_phase6_runtime_stub_emits_planning_audit() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run()

    assert result["run_status"] == "succeeded"
    assert result["collection_plan"] is not None
    assert result["llm_planning_audits"]
