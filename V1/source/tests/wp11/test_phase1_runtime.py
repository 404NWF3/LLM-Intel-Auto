from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime


def test_phase1_stub_run_succeeds() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run()
    saved_state = runtime.get_state(result["run_id"])

    assert result["run_status"] == "succeeded"
    assert result["processed_count"] > 0
    assert result["collection_plan"] is not None
    assert result["node_results"]
    assert all("artifact_ref" in item for item in result["raw_items"])
    assert result["source_health_dashboard"]
    assert saved_state["run_id"] == result["run_id"]


def test_phase1_reflection_loop_rewrites_once() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run(force_low_yield=True)
    dispatch_runs = [
        node
        for node in result["node_results"]
        if node["node_name"] == "dispatch_collection"
    ]

    assert result["run_status"] == "succeeded"
    assert result["reflection_round"] == 1
    assert len(dispatch_runs) == 2
    assert result["collection_plan"]["source_plans"][0]["rewrite_reason"] in {
        "low_yield",
        "high_noise",
    }


def test_phase1_transient_failure_recovers_with_retry() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run(fail_once_nodes=["collect_from_sources"])
    collector_attempts = {
        key: value
        for key, value in result["node_attempts"].items()
        if key.startswith("collect_") and key.endswith("_sources")
    }

    assert result["run_status"] == "succeeded"
    assert any(value == 2 for value in collector_attempts.values())
    assert result["errors"] == []


def test_phase1_persistent_failure_is_recorded() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run(always_fail_nodes=["collect_from_sources"])

    assert result["run_status"] == "partial_success"
    assert result["errors"]
    assert result["errors"][0]["node_name"].startswith("collect_")


def test_phase1_recover_from_specific_node() -> None:
    runtime = Phase1GraphRuntime()
    failed = runtime.invoke_stub_run(always_fail_nodes=["collect_from_sources"])

    recovered = runtime.recover(
        failed["run_id"],
        resume_from_node="store_raw_records",
        runtime_context_override=failed["runtime_context"],
    )

    assert recovered["run_status"] == "succeeded"
