from __future__ import annotations

from typing import Any

from backend.agents.saads_wp12.state import SecurityEvalState


_TOP_LEVEL_KEYS = [
    "run_id",
    "tenant_id",
    "scenario_id",
    "attack_id",
    "intel_normalized",
    "threat_understanding",
    "scope_assessment",
    "execution_assessment",
    "evidence_and_context",
    "uncertainty_report",
    "test_package",
    "package_validation",
    "package_version",
    "reflection_round",
    "max_reflection_rounds",
    "risk_flags",
    "audit_log",
]

_METADATA_KEYS = [
    "generator_name",
    "llm_enabled",
    "llm_override_fields",
    "llm_fallback_reason",
    "llm_fallback_detail",
    "llm_validation_errors",
    "llm_raw_fields",
    "llm_raw_type",
    "input_contract",
]


def _copy_if_present(source: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


def _compact_test_package_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(metadata, _METADATA_KEYS)


def _compact_evidence_and_context(evidence_and_context: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(
        evidence_and_context,
        [
            "component_context_summary",
            "seed_asset_summary",
            "stix_summary",
            "candidate_families",
            "taxonomy_context",
            "planning_focus",
            "surface_and_mechanism_summary",
        ],
    )


def _compact_uncertainty_report(uncertainty_report: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(
        uncertainty_report,
        [
            "missing_knowledge",
            "risk_flags",
            "known_gaps",
        ],
    )


def _compact_test_package(test_package: dict[str, Any]) -> dict[str, Any]:
    compact_package = _copy_if_present(
        test_package,
        [
            "package_id",
            "package_kind",
            "objective",
            "attack_hypothesis",
            "family_specific_strategy",
            "payload_plan",
            "execution_plan",
            "success_criteria",
            "failure_signals",
            "assumptions",
            "environment_assumptions",
            "recommended_follow_up",
            "evidence_collection_plan",
            "script_blueprint",
            "target_artifacts",
            "generation_mode",
            "metadata",
        ],
    )
    if isinstance(compact_package.get("metadata"), dict):
        compact_package["metadata"] = _compact_test_package_metadata(compact_package["metadata"])
    return compact_package


def build_compact_export_state(state: SecurityEvalState) -> dict[str, Any]:
    exported = _copy_if_present(state, _TOP_LEVEL_KEYS)

    evidence_and_context = exported.get("evidence_and_context")
    if isinstance(evidence_and_context, dict):
        exported["evidence_and_context"] = _compact_evidence_and_context(evidence_and_context)

    uncertainty_report = exported.get("uncertainty_report")
    if isinstance(uncertainty_report, dict):
        exported["uncertainty_report"] = _compact_uncertainty_report(uncertainty_report)

    test_package = exported.get("test_package")
    if isinstance(test_package, dict):
        exported["test_package"] = _compact_test_package(test_package)

    return exported


def _compact_threat_understanding(threat_understanding: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(
        threat_understanding,
        [
            "threat_summary",
            "attack_mechanism",
            "attack_mechanism_type",
            "target_surface",
            "target_surface_type",
            "taxonomy",
            "primary_test_question",
            "highest_value_validation_target",
            "recommended_test_strategy",
        ],
    )


def _compact_execution_assessment(execution_assessment: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(
        execution_assessment,
        [
            "execution_eligibility",
            "execution_blockers",
            "test_readiness",
            "execution_mode",
        ],
    )


def _compact_execution_plan(execution_plan: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(
        execution_plan,
        [
            "entry_strategy",
            "runner_type",
            "parameterization",
            "steps",
        ],
    )


def _compact_evidence_collection_plan(evidence_collection_plan: dict[str, Any]) -> dict[str, Any]:
    return _copy_if_present(
        evidence_collection_plan,
        [
            "collection_mode",
            "capture_strategy",
            "evidence_types",
            "secondary_evidence_focus",
        ],
    )


def _compact_test_package_for_presentation(test_package: dict[str, Any]) -> dict[str, Any]:
    compact_package = _copy_if_present(
        test_package,
        [
            "package_id",
            "package_kind",
            "generation_mode",
            "objective",
            "attack_hypothesis",
            "family_specific_strategy",
            "payload_plan",
            "execution_plan",
            "success_criteria",
            "failure_signals",
            "assumptions",
            "recommended_follow_up",
            "evidence_collection_plan",
            "target_artifacts",
        ],
    )
    execution_plan = compact_package.get("execution_plan")
    if isinstance(execution_plan, dict):
        compact_package["execution_plan"] = _compact_execution_plan(execution_plan)
    evidence_plan = compact_package.get("evidence_collection_plan")
    if isinstance(evidence_plan, dict):
        compact_package["evidence_collection_plan"] = _compact_evidence_collection_plan(evidence_plan)
    return compact_package


def build_presentation_export_state(state: SecurityEvalState) -> dict[str, Any]:
    compact = build_compact_export_state(state)
    presented = _copy_if_present(
        compact,
        [
            "run_id",
            "attack_id",
            "scope_assessment",
            "execution_assessment",
            "threat_understanding",
            "evidence_and_context",
            "uncertainty_report",
            "test_package",
            "package_validation",
        ],
    )

    threat_understanding = presented.get("threat_understanding")
    if isinstance(threat_understanding, dict):
        presented["threat_understanding"] = _compact_threat_understanding(threat_understanding)

    execution_assessment = presented.get("execution_assessment")
    if isinstance(execution_assessment, dict):
        presented["execution_assessment"] = _compact_execution_assessment(execution_assessment)

    evidence_and_context = presented.get("evidence_and_context")
    if isinstance(evidence_and_context, dict):
        presented["evidence_and_context"] = _compact_evidence_and_context(evidence_and_context)

    test_package = presented.get("test_package")
    if isinstance(test_package, dict):
        presented["test_package"] = _compact_test_package_for_presentation(test_package)

    uncertainty_report = presented.get("uncertainty_report")
    if isinstance(uncertainty_report, dict):
        presented["uncertainty_report"] = _copy_if_present(
            uncertainty_report,
            ["known_gaps", "missing_knowledge"],
        )

    return presented
