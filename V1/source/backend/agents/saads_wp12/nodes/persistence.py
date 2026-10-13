from __future__ import annotations

import json
from pathlib import Path

from backend.agents.saads_wp12.reporting.llm_plan_writer import generate_plan_markdown
from backend.agents.saads_wp12.reporting.state_export import build_presentation_export_state
from backend.agents.saads_wp12.state import SecurityEvalState


def finalize_plan_result(state: SecurityEvalState) -> dict:
    package_validation = state.get("package_validation") or {}
    test_package = state.get("test_package") or {}

    if not package_validation.get("valid", False):
        verdict = "invalid"
    elif test_package.get("package_kind") == "triage":
        verdict = "triaged"
    else:
        verdict = "planned"

    return {
        "verdict": verdict,
        "env_status": "not_applicable_plan_generation",
    }


def persist_plan_artifacts(state: SecurityEvalState) -> dict:
    run_id = state["run_id"]
    attack_id = state["attack_id"]
    run_dir = Path("artifacts") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_state_path = run_dir / f"{attack_id}_state_raw.json"
    presentation_state_path = run_dir / f"{attack_id}_state_presentation.json"
    plan_path = run_dir / f"{attack_id}_plan.md"

    raw_state_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    presentation_state_path.write_text(
        json.dumps(build_presentation_export_state(state), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    plan_path.write_text(
        generate_plan_markdown(state),
        encoding="utf-8",
    )

    return {
        "persistence_path": str(run_dir),
        "raw_state_path": str(raw_state_path),
        "presentation_state_path": str(presentation_state_path),
        "plan_path": str(plan_path),
    }
