from __future__ import annotations

from typing import Any, TypedDict


class SecurityEvalState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    scenario_id: str
    threat_id: str
    attack_id: str

    intel_raw: dict[str, Any]
    intel_normalized: dict[str, Any]

    threat_understanding: dict[str, Any]
    threat_profile: dict[str, Any]
    scope_assessment: dict[str, Any]
    execution_assessment: dict[str, Any]
    evidence_and_context: dict[str, Any]
    uncertainty_report: dict[str, Any]
    attack_family: str
    in_scope: bool
    supported_family: str
    scope_reason: str
    target_surface: str
    confidence: float
    candidate_families: list[dict[str, Any]]
    classification_rationale: dict[str, Any]
    missing_knowledge: list[dict[str, Any]]
    execution_eligibility: str
    test_readiness: str
    generation_route: str
    can_build_env: bool
    should_execute: bool
    execution_mode: str

    test_package: dict[str, Any]
    package_validation: dict[str, Any]
    package_version: int

    env_status: str
    verdict: str

    reflection_round: int
    max_reflection_rounds: int

    risk_flags: list[str]
    audit_log: list[dict[str, Any]]
    persistence_path: str
    raw_state_path: str
    presentation_state_path: str
    plan_path: str
