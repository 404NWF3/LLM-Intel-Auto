from __future__ import annotations

from backend.agents.saads_wp12.state import SecurityEvalState


COMMON_REQUIRED_FIELDS = [
    "package_id",
    "package_kind",
    "attack_family",
    "target_surface",
    "objective",
    "attack_hypothesis",
    "payload_plan",
    "execution_plan",
    "success_criteria",
    "failure_signals",
    "evidence_hooks",
    "assumptions",
    "environment_assumptions",
    "known_gaps",
    "recommended_follow_up",
    "evidence_collection_plan",
    "script_blueprint",
    "target_artifacts",
    "family_specific_strategy",
    "metadata",
]

PAYLOAD_REQUIRED_FIELDS = [
    "payload_id",
    "payload_type",
    "payload_source",
    "payload_template",
    "payload_variables",
    "delivery_channel",
    "risk_level",
    "use_mode",
    "expected_effect",
]

EXECUTION_PLAN_REQUIRED_FIELDS = [
    "entry_strategy",
    "runner_type",
    "runner_command_template",
    "input_contract",
    "expected_outputs",
    "timeout_seconds",
    "retry_budget",
    "parameterization",
    "execution_steps",
    "cleanup_steps",
    "execution_eligibility",
]


def _validate_payload_plan(payload_plan: list[dict], validation_errors: list[str]) -> None:
    if not payload_plan:
        validation_errors.append("payload_plan must contain at least one payload entry.")
        return
    for index, payload in enumerate(payload_plan, start=1):
        for field in PAYLOAD_REQUIRED_FIELDS:
            if field not in payload:
                validation_errors.append(f"payload_plan[{index}] is missing required field '{field}'.")
        if "payload_variables" in payload and not isinstance(payload.get("payload_variables"), list):
            validation_errors.append(f"payload_plan[{index}].payload_variables must be a list.")


def _validate_execution_plan(execution_plan: dict, validation_errors: list[str]) -> None:
    for field in EXECUTION_PLAN_REQUIRED_FIELDS:
        if field not in execution_plan:
            validation_errors.append(f"execution_plan is missing required field '{field}'.")
    if execution_plan.get("timeout_seconds", 0) < 0:
        validation_errors.append("execution_plan.timeout_seconds must be non-negative.")
    if execution_plan.get("retry_budget", 0) < 0:
        validation_errors.append("execution_plan.retry_budget must be non-negative.")
    if execution_plan.get("execution_steps") is not None and not execution_plan.get("execution_steps"):
        validation_errors.append("execution_plan.execution_steps must not be empty.")


def _validate_blueprint(test_package: dict, validation_errors: list[str]) -> None:
    blueprint = test_package.get("script_blueprint", {})
    file_plan = blueprint.get("file_plan")
    if not isinstance(file_plan, list) or not file_plan:
        validation_errors.append("script_blueprint.file_plan must contain at least one file plan entry.")

    evidence_plan = test_package.get("evidence_collection_plan", {})
    required_hooks = evidence_plan.get("required_hooks", [])
    hooks = test_package.get("evidence_hooks", [])
    if required_hooks and not set(required_hooks).issubset(set(hooks)):
        validation_errors.append("evidence_hooks must include all evidence_collection_plan.required_hooks entries.")

    target_artifacts = test_package.get("target_artifacts", [])
    if not isinstance(target_artifacts, list) or not target_artifacts:
        validation_errors.append("target_artifacts must contain at least one planned output artifact.")


def _validate_family_specific_contract(test_package: dict, validation_errors: list[str]) -> None:
    package_kind = test_package.get("package_kind", "")
    if package_kind == "triage":
        return

    attack_family = test_package.get("attack_family", "")
    payload_types = {payload.get("payload_type") for payload in test_package.get("payload_plan", [])}
    step_actions = {
        step.get("action") for step in test_package.get("execution_plan", {}).get("execution_steps", [])
    }
    evidence_hooks = set(test_package.get("evidence_hooks", []))
    file_paths = {
        file_plan.get("path") for file_plan in test_package.get("script_blueprint", {}).get("file_plan", [])
    }
    criterion_ids = {
        criterion.get("criterion_id") for criterion in test_package.get("success_criteria", [])
    }
    failure_ids = {
        signal.get("signal_id") for signal in test_package.get("failure_signals", [])
    }

    family_contracts = {
        "prompt_injection": {
            "payload_types": {"context_binding_plan"},
            "step_actions": {
                "bind_retrieved_context_slot",
                "assemble_retrieval_context_with_hostile_overlay",
                "evaluate_instruction_priority_inversion",
                "compare_safe_and_injected_outputs",
            },
            "evidence_hooks": {"retrieval_trace", "context_snapshot"},
            "file_paths": {"assets/context_binding.json", "reports/retrieval_trace.json"},
            "criterion_ids": {
                "context-priority-inversion-confirmed",
                "injected-output-differs-from-safe-baseline",
            },
            "failure_ids": {"context-binding-missing", "baseline-output-unchanged"},
        },
        "long_horizon_dialogue": {
            "payload_types": {"dialogue_turn_schedule", "dialogue_state_tracker"},
            "step_actions": {
                "render_dialogue_turn_schedule",
                "bind_dialogue_state_checkpoints",
                "evaluate_dialogue_state_progression",
                "compare_turn_by_turn_safety_delta",
            },
            "evidence_hooks": {"dialogue_transcript", "turn_state_snapshot"},
            "file_paths": {
                "assets/dialogue_plan.json",
                "assets/dialogue_state_tracker.json",
                "reports/dialogue_transcript.json",
            },
            "criterion_ids": {"dialogue-checkpoints-covered", "dialogue-output-delta-confirmed"},
            "failure_ids": {"dialogue-checkpoints-missing", "dialogue-output-static"},
        },
        "tool_hijack": {
            "payload_types": {"tool_argument_map", "tool_trace_expectation"},
            "step_actions": {
                "render_tool_argument_map",
                "bind_expected_tool_trace_markers",
                "inspect_tool_call_trace",
                "compare_planned_and_observed_tool_usage",
            },
            "evidence_hooks": {"tool_call_trace", "tool_argument_snapshot"},
            "file_paths": {
                "configs/tool_plan.json",
                "configs/tool_trace_expectation.json",
                "reports/tool_call_trace.json",
            },
            "criterion_ids": {"planned-tool-path-matched", "tool-execution-delta-confirmed"},
            "failure_ids": {"tool-plan-unbound", "tool-usage-static"},
        },
    }
    contract = family_contracts.get(attack_family)
    if not contract:
        return

    for payload_type in contract["payload_types"]:
        if payload_type not in payload_types:
            validation_errors.append(
                f"{attack_family} package must include payload_plan entry with payload_type='{payload_type}'."
            )
    for action in contract["step_actions"]:
        if action not in step_actions:
            validation_errors.append(
                f"{attack_family} package must include execution step action='{action}'."
            )
    for hook in contract["evidence_hooks"]:
        if hook not in evidence_hooks:
            validation_errors.append(
                f"{attack_family} package must include evidence_hook='{hook}'."
            )
    for file_path in contract["file_paths"]:
        if file_path not in file_paths:
            validation_errors.append(
                f"{attack_family} package must include script_blueprint file '{file_path}'."
            )
    for criterion_id in contract["criterion_ids"]:
        if criterion_id not in criterion_ids:
            validation_errors.append(
                f"{attack_family} package must include success criterion '{criterion_id}'."
            )
    for failure_id in contract["failure_ids"]:
        if failure_id not in failure_ids:
            validation_errors.append(
                f"{attack_family} package must include failure signal '{failure_id}'."
            )


def validate_test_package(state: SecurityEvalState) -> dict:
    test_package = state.get("test_package", {})
    missing_fields = [field for field in COMMON_REQUIRED_FIELDS if field not in test_package]
    validation_errors: list[str] = []

    package_kind = test_package.get("package_kind", "")
    generation_mode = test_package.get("generation_mode", "")
    execution_plan = test_package.get("execution_plan", {})
    payload_plan = test_package.get("payload_plan", [])

    if not missing_fields:
        _validate_payload_plan(payload_plan, validation_errors)
        _validate_execution_plan(execution_plan, validation_errors)
        _validate_blueprint(test_package, validation_errors)
        _validate_family_specific_contract(test_package, validation_errors)

    if package_kind == "triage":
        if generation_mode != "triage":
            validation_errors.append("triage package must use generation_mode='triage'.")
        if execution_plan.get("entry_strategy") != "do_not_execute":
            validation_errors.append("triage package must use execution_plan.entry_strategy='do_not_execute'.")
        if execution_plan.get("runner_type") != "analysis_only":
            validation_errors.append("triage package must use execution_plan.runner_type='analysis_only'.")
        if execution_plan.get("retry_budget") not in {0, None}:
            validation_errors.append("triage package must use execution_plan.retry_budget=0.")
        if payload_plan:
            first_payload = payload_plan[0]
            if first_payload.get("use_mode") != "analysis_only":
                validation_errors.append("triage package payload plan must stay in analysis_only mode.")
        if test_package.get("script_blueprint", {}).get("blueprint_kind") != "analysis_only":
            validation_errors.append("triage package script_blueprint.blueprint_kind must be 'analysis_only'.")
    else:
        if generation_mode not in {"standard", "conservative"}:
            validation_errors.append("non-triage package must use generation_mode='standard' or 'conservative'.")
        if execution_plan.get("entry_strategy") == "do_not_execute":
            validation_errors.append("non-triage package must not use do_not_execute entry strategy.")
        if not execution_plan.get("runner_command_template"):
            validation_errors.append("non-triage package must define execution_plan.runner_command_template.")
        if test_package.get("script_blueprint", {}).get("blueprint_kind") != "runtime_execution":
            validation_errors.append(
                "non-triage package script_blueprint.blueprint_kind must be 'runtime_execution'."
            )
        execution_assessment = test_package.get("metadata", {}).get("execution_assessment", {})
        if not execution_assessment.get("has_aibom_context", True) and package_kind == "standard":
            validation_errors.append("standard package requires execution_assessment.has_aibom_context=True.")
        if generation_mode == "conservative":
            if execution_plan.get("entry_strategy") != "assumption_gated_probe":
                validation_errors.append(
                    "conservative package must use execution_plan.entry_strategy='assumption_gated_probe'."
                )
            if execution_plan.get("retry_budget") not in {0, 1}:
                validation_errors.append("conservative package must keep execution_plan.retry_budget <= 1.")
            if execution_plan.get("parameterization", {}).get("execution_profile") != "verification_probe":
                validation_errors.append(
                    "conservative package must use execution_plan.parameterization.execution_profile='verification_probe'."
                )
            if any(payload.get("risk_level") not in {"none", "low"} for payload in payload_plan):
                validation_errors.append("conservative package payloads must stay at risk_level 'low' or below.")
            conservative_actions = {step.get("action") for step in execution_plan.get("execution_steps", [])}
            if "verify_target_and_asset_readiness" not in conservative_actions:
                validation_errors.append(
                    "conservative package must include a verify_target_and_asset_readiness execution step."
                )
            if "decide_whether_to_escalate" not in conservative_actions:
                validation_errors.append(
                    "conservative package must include a decide_whether_to_escalate execution step."
                )
        if generation_mode == "standard":
            if execution_plan.get("entry_strategy") != "single_script_iteration":
                validation_errors.append(
                    "standard package must use execution_plan.entry_strategy='single_script_iteration'."
                )
            if execution_plan.get("retry_budget", 0) < 2:
                validation_errors.append("standard package must keep execution_plan.retry_budget >= 2.")
            if execution_plan.get("parameterization", {}).get("execution_profile") != "full_runtime_execution":
                validation_errors.append(
                    "standard package must use execution_plan.parameterization.execution_profile='full_runtime_execution'."
                )
            if not any(payload.get("risk_level") == "high" for payload in payload_plan):
                validation_errors.append("standard package must include at least one high-risk primary payload.")
            standard_actions = {step.get("action") for step in execution_plan.get("execution_steps", [])}
            if "score_family_outcome_against_success_criteria" not in standard_actions:
                validation_errors.append(
                    "standard package must include a score_family_outcome_against_success_criteria execution step."
                )

    return {
        "package_validation": {
            "valid": not missing_fields and not validation_errors,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
        }
    }
