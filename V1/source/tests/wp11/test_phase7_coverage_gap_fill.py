"""Tests for Phase 7 -- coverage gap fill and LLM-aware gap analysis."""

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

CoverageReadModelService = import_module(
    "agents.intel_agents.services.coverage_read_model_service"
).CoverageReadModelService
GapScoringService = import_module(
    "agents.intel_agents.services.gap_scoring_service"
).GapScoringService
CoverageAnalystAgent = import_module(
    "agents.intel_agents.agents.coverage_analyst_agent"
).CoverageAnalystAgent
CoverageGapDTO = import_module("agents.intel_agents.schemas.alert").CoverageGapDTO
LlmCoverageAnalysisAuditDTO = import_module(
    "agents.intel_agents.schemas.coverage"
).LlmCoverageAnalysisAuditDTO
RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO
build_initial_state = import_module(
    "agents.intel_agents.orchestrator.state"
).build_initial_state
refresh_coverage_view_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).refresh_coverage_view_node
coverage_gap_analysis_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).coverage_gap_analysis_node
Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime


def _stable_record(
    *,
    stable_attack_id: str,
    taxonomy_code: str,
    taxonomy_name: str,
    source_coverage: list[str],
    bom_names: list[str],
    severity_level: str = "high",
    attack_family: str = "prompt_injection",
) -> dict[str, Any]:
    return {
        "stable_attack_id": stable_attack_id,
        "stable_attack_code": stable_attack_id,
        "canonical_name": f"{taxonomy_name} case {stable_attack_id}",
        "attack_family": attack_family,
        "severity_level": severity_level,
        "summary": f"{taxonomy_name} issue",
        "description": f"{taxonomy_name} description",
        "taxonomy_items": [
            {
                "taxonomy_type": "OWASP_LLM",
                "taxonomy_code": taxonomy_code,
                "taxonomy_name": taxonomy_name,
                "confidence_score": 0.9,
                "is_primary": True,
            }
        ],
        "cvss_hint": None,
        "bom_mentions": [
            {
                "mentioned_name": name,
                "mentioned_vendor": None,
                "mentioned_version": None,
                "confidence_score": 0.8,
                "reason_code": "name_mention",
            }
            for name in bom_names
        ],
        "evidence_refs": [f"artifact://{stable_attack_id}"],
        "source_coverage": source_coverage,
        "related_raw_ids": [f"raw-{stable_attack_id}"],
        "member_attack_codes": [stable_attack_id],
        "last_decision": "merge",
        "confidence_score": 0.88,
    }


class FakeCoverageAnalyst:
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

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.error and self.error != "validate_failed":
            raise RuntimeError(self.error)
        if self.result is None:
            raise AssertionError("No fake decision configured")
        return self.result


def test_phase7_coverage_read_model_builds_views() -> None:
    service = CoverageReadModelService()
    stable = [
        _stable_record(
            stable_attack_id="stable-1",
            taxonomy_code="OWASP-LLM-01",
            taxonomy_name="Prompt Injection",
            source_coverage=["github_advisories", "arxiv"],
            bom_names=["langchain", "openai"],
        )
    ]

    coverage_rows = service.build_taxonomy_component_source_view(stable)
    vendor_rows = service.build_vendor_model_source_view(stable)

    assert coverage_rows
    assert vendor_rows
    assert coverage_rows[0]["coverage_axis"] == "taxonomy_component_source"
    assert "source_name" in vendor_rows[0]


def test_phase7_gap_scoring_produces_ranked_candidates() -> None:
    scorer = GapScoringService()
    coverage_rows = [
        {
            "taxonomy_code": "OWASP-LLM-01",
            "taxonomy_name": "Prompt Injection",
            "attack_family": "prompt_injection",
            "source_name": "github_advisories",
            "component_family": "langchain",
            "attack_count": 1,
            "high_severity_count": 1,
            "corroborated_attack_count": 0,
        }
    ]
    vendor_rows = [
        {
            "vendor_name": "OpenAI",
            "model_family": "GPT",
            "framework_family": None,
            "source_name": "github_advisories",
            "taxonomy_code": "OWASP-LLM-01",
            "attack_count": 0,
            "high_severity_count": 0,
            "corroborated_attack_count": 0,
            "version_mapped_count": 0,
        }
    ]

    ranked = scorer.rank_gap_candidates(
        [
            *scorer.score_taxonomy_gaps(coverage_rows),
            *scorer.score_vendor_model_gaps(vendor_rows),
        ]
    )

    assert ranked
    assert ranked[0]["estimated_gap_fill_roi"] >= ranked[-1]["estimated_gap_fill_roi"]


def test_phase7_taxonomy_gap_scoring_deduplicates_stable_attacks() -> None:
    service = CoverageReadModelService()
    scorer = GapScoringService()
    stable = [
        _stable_record(
            stable_attack_id="stable-1",
            taxonomy_code="OWASP-LLM-01",
            taxonomy_name="Prompt Injection",
            source_coverage=["github_advisories", "arxiv"],
            bom_names=["langchain", "openai"],
        )
    ]

    coverage_rows = service.build_taxonomy_component_source_view(stable)
    ranked = scorer.score_taxonomy_gaps(coverage_rows)

    assert len(coverage_rows) == 4
    assert ranked[0]["current_attack_count"] == 1
    assert ranked[0]["source_diversity_gap"] == pytest.approx(0.3333, abs=1e-4)


def test_phase7_vendor_model_gap_scoring_preserves_taxonomy_dimension() -> None:
    service = CoverageReadModelService()
    scorer = GapScoringService()
    stable = [
        _stable_record(
            stable_attack_id="stable-1",
            taxonomy_code="OWASP-LLM-01",
            taxonomy_name="Prompt Injection",
            source_coverage=["github_advisories"],
            bom_names=["openai"],
        ),
        _stable_record(
            stable_attack_id="stable-2",
            taxonomy_code="OWASP-LLM-02",
            taxonomy_name="Insecure Output Handling",
            source_coverage=["arxiv"],
            bom_names=["openai"],
        ),
    ]

    vendor_rows = service.build_vendor_model_source_view(stable)
    ranked = scorer.score_vendor_model_gaps(vendor_rows)

    assert len(ranked) == 2
    assert {row["taxonomy_code"] for row in ranked} == {"OWASP-LLM-01", "OWASP-LLM-02"}
    assert len({row["gap_id"] for row in ranked}) == 2


def test_phase7_rules_only_coverage_analyst_generates_dispatch_plan() -> None:
    agent = CoverageAnalystAgent(strategy="rules_only")
    gaps, dispatch, audits = agent.analyze(
        [
            {
                "gap_id": "taxonomy::owasp-llm-01",
                "gap_axis": "taxonomy",
                "taxonomy_code": "OWASP-LLM-01",
                "taxonomy_name": "Prompt Injection",
                "attack_family": "prompt_injection",
                "current_attack_count": 0,
                "target_attack_count": 3,
                "gap_score": 0.95,
                "source_diversity_gap": 0.8,
                "component_coverage_gap": 0.7,
                "corroboration_gap": 0.6,
                "vendor_model_gap": 0.0,
                "severity_pressure": 0.5,
                "recent_activity_score": 0.5,
                "estimated_gap_fill_roi": 0.82,
                "evidence_summary": "Prompt injection gap is large.",
            }
        ],
        runtime_context=RuntimeContextDTO.default_stub().model_dump(mode="python"),
        max_gap_fill_plans=3,
        min_roi_threshold=0.65,
    )

    assert gaps
    assert dispatch
    assert audits
    CoverageGapDTO.model_validate(gaps[0])


def test_phase7_llm_required_coverage_analyst_uses_llm_output() -> None:
    fake = FakeCoverageAnalyst(
        {
            "should_dispatch_gap_fill": True,
            "gap_type": "taxonomy",
            "diagnosis": "taxonomy under-covered in structured and paper sources",
            "recommended_sources": ["github_advisories", "arxiv"],
            "recommended_queries": [
                "Prompt Injection large language model",
                "Prompt Injection vulnerability disclosure",
            ],
            "recommended_query_intents": ["taxonomy_anchor", "evidence_corroboration"],
            "expected_evidence_type": ["advisory", "paper"],
            "recommended_time_window_days": 21,
            "estimated_gap_fill_roi": 0.9,
            "confidence": 0.93,
            "reason": "high severity and low source diversity justify targeted gap fill",
        }
    )
    agent = CoverageAnalystAgent(strategy="llm_required", analyst=fake)
    gaps, dispatch, audits = agent.analyze(
        [
            {
                "gap_id": "taxonomy::owasp-llm-01",
                "gap_axis": "taxonomy",
                "taxonomy_code": "OWASP-LLM-01",
                "taxonomy_name": "Prompt Injection",
                "attack_family": "prompt_injection",
                "current_attack_count": 0,
                "target_attack_count": 3,
                "gap_score": 0.95,
                "source_diversity_gap": 0.8,
                "component_coverage_gap": 0.7,
                "corroboration_gap": 0.6,
                "vendor_model_gap": 0.0,
                "severity_pressure": 0.5,
                "recent_activity_score": 0.5,
                "estimated_gap_fill_roi": 0.82,
                "evidence_summary": "Prompt injection gap is large.",
            }
        ],
        runtime_context=RuntimeContextDTO.default_stub().model_dump(mode="python"),
        max_gap_fill_plans=3,
        min_roi_threshold=0.65,
    )

    assert fake.calls
    assert gaps[0]["recommended_sources"] == ["github_advisories", "arxiv"]
    assert dispatch[0]["recommended_query_intents"] == [
        "taxonomy_anchor",
        "evidence_corroboration",
    ]
    LlmCoverageAnalysisAuditDTO.model_validate(audits[0])


def test_phase7_llm_optional_degrades_on_failure() -> None:
    agent = CoverageAnalystAgent(
        strategy="llm_optional",
        analyst=FakeCoverageAnalyst(error="coverage_llm_failed"),
    )
    _, dispatch, audits = agent.analyze(
        [
            {
                "gap_id": "taxonomy::owasp-llm-01",
                "gap_axis": "taxonomy",
                "taxonomy_code": "OWASP-LLM-01",
                "taxonomy_name": "Prompt Injection",
                "attack_family": "prompt_injection",
                "current_attack_count": 0,
                "target_attack_count": 3,
                "gap_score": 0.95,
                "source_diversity_gap": 0.8,
                "component_coverage_gap": 0.7,
                "corroboration_gap": 0.6,
                "vendor_model_gap": 0.0,
                "severity_pressure": 0.5,
                "recent_activity_score": 0.5,
                "estimated_gap_fill_roi": 0.82,
                "evidence_summary": "Prompt injection gap is large.",
            }
        ],
        runtime_context=RuntimeContextDTO.default_stub().model_dump(mode="python"),
        max_gap_fill_plans=3,
        min_roi_threshold=0.65,
    )

    assert dispatch
    assert audits[0]["strategy_executed"] == "rules_only_degraded"
    assert audits[0]["fallback_reason"] == "coverage_llm_failed"


def test_phase7_refresh_coverage_view_node_updates_runtime_context() -> None:
    state = build_initial_state(
        runtime_context=RuntimeContextDTO.default_stub().model_dump(mode="python")
    )
    state["stable_attack_records"] = [
        _stable_record(
            stable_attack_id="stable-1",
            taxonomy_code="OWASP-LLM-01",
            taxonomy_name="Prompt Injection",
            source_coverage=["github_advisories", "arxiv"],
            bom_names=["langchain", "openai"],
        )
    ]

    result = refresh_coverage_view_node(state)

    assert result["runtime_context"]["coverage_snapshot"]
    assert result["runtime_context"]["vendor_model_coverage_rows"]
    assert result["runtime_context"]["coverage_refreshed_at"]


def test_phase7_coverage_gap_analysis_node_emits_gaps_dispatch_and_audits() -> None:
    ctx = RuntimeContextDTO.default_stub().model_dump(mode="python")
    ctx["coverage_strategy"] = "rules_only"
    ctx["coverage_snapshot"] = [
        {
            "coverage_axis": "taxonomy_component_source",
            "taxonomy_code": "OWASP-LLM-01",
            "taxonomy_name": "Prompt Injection",
            "attack_family": "prompt_injection",
            "source_name": "github_advisories",
            "component_family": "langchain",
            "attack_count": 1,
            "high_severity_count": 1,
            "source_diversity_count": 1,
            "corroborated_attack_count": 0,
            "version_mapped_count": 0,
            "last_seen_at": None,
        }
    ]
    ctx["vendor_model_coverage_rows"] = [
        {
            "vendor_name": "OpenAI",
            "model_family": "GPT",
            "framework_family": None,
            "source_name": "github_advisories",
            "taxonomy_code": "OWASP-LLM-01",
            "attack_count": 0,
            "high_severity_count": 0,
            "corroborated_attack_count": 0,
            "version_mapped_count": 0,
        }
    ]
    state = build_initial_state(runtime_context=ctx)

    result = coverage_gap_analysis_node(state)

    assert result["coverage_gaps"]
    assert result["gap_fill_dispatch_plans"]
    assert result["llm_coverage_analysis_audits"]
    assert result["gap_fill_needed"] is True
    assert result["reflection_needed"] is False
    CoverageGapDTO.model_validate(result["coverage_gaps"][0])
    LlmCoverageAnalysisAuditDTO.model_validate(
        result["llm_coverage_analysis_audits"][0]
    )


def test_phase7_runtime_force_gap_fill_emits_gap_state() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run(force_gap_fill=True)

    assert result["run_status"] == "succeeded"
    assert "coverage_gaps" in result
    assert "gap_fill_dispatch_plans" in result
    assert "llm_coverage_analysis_audits" in result


def test_phase7_runtime_gap_fill_loops_back_into_targeted_collection() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run(force_gap_fill=True)

    assert result["run_status"] == "succeeded"
    assert result["gap_fill_round"] == 1
    assert result["collection_plan"]["run_mode"] == "gap_fill"
    assert result["collection_plan"]["reflection_enabled"] is False
    assert result["runtime_context"]["coverage_feedback_rows"]
    assert result["runtime_context"]["gap_fill_dispatch_plans"]
    assert all(
        row["fetch_mode"] == "targeted_gap_fill"
        for row in result["collection_plan"]["source_plans"]
    )
    assert all(
        row["query_provenance"] == "phase7_gap_fill_dispatch"
        for row in result["collection_plan"]["source_plans"]
    )


def test_phase7_runtime_state_contains_phase7_fields() -> None:
    state = build_initial_state()
    assert "coverage_gaps" in state
    assert "gap_fill_dispatch_plans" in state
    assert "llm_coverage_analysis_audits" in state
    assert "gap_fill_needed" in state
    assert "gap_fill_rationale" in state
    assert state["gap_fill_dispatch_plans"] == []
    assert state["llm_coverage_analysis_audits"] == []


def test_phase7_rules_decision_filters_unknown_sources_from_registry() -> None:
    gap_candidates = [
        {
            "gap_id": "vendor_model::openai::owasp-llm-01",
            "gap_axis": "vendor_model",
            "taxonomy_code": "OWASP-LLM-01",
            "taxonomy_name": "Prompt Injection",
            "vendor_name": "OpenAI",
            "model_family": "GPT",
            "framework_family": None,
            "current_attack_count": 0,
            "target_attack_count": 2,
            "gap_score": 1.0,
            "source_diversity_gap": 1.0,
            "component_coverage_gap": 0.0,
            "corroboration_gap": 1.0,
            "vendor_model_gap": 1.0,
            "severity_pressure": 0.5,
            "recent_activity_score": 0.2,
            "estimated_gap_fill_roi": 0.9,
            "evidence_summary": "vendor/model gap",
        }
    ]
    runtime_context = RuntimeContextDTO.default_stub().model_dump(mode="python")
    runtime_context["source_registry"] = [
        {
            "source_name": "github_advisories",
            "source_type": "code",
            "enabled": True,
            "default_max_results": 5,
            "default_time_window_days": 7,
        },
        {
            "source_name": "arxiv",
            "source_type": "paper",
            "enabled": True,
            "default_max_results": 5,
            "default_time_window_days": 7,
        },
    ]

    _, dispatch_plans, _ = CoverageAnalystAgent(strategy="rules_only").analyze(
        gap_candidates,
        runtime_context=runtime_context,
        max_gap_fill_plans=1,
        min_roi_threshold=0.65,
    )

    assert dispatch_plans
    assert set(dispatch_plans[0]["recommended_sources"]) <= {
        "github_advisories",
        "arxiv",
    }
