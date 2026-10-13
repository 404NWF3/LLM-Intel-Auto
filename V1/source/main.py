from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

load_dotenv(dotenv_path=ROOT / ".env", override=False)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.agents.intel_agents.orchestrator.runtime import Phase1GraphRuntime
from backend.agents.intel_agents.orchestrator.state import build_initial_state
from backend.agents.intel_agents.schemas.runtime import RuntimeContextDTO

SCENARIOS: dict[str, dict[str, Any]] = {
    "normal": {
        "description": "Standard stub run. Enables enrichment subgraphs when LLM is available.",
        "fail_once_nodes": [],
        "always_fail_nodes": [],
        "force_low_yield": False,
        "force_gap_fill": False,
        "force_no_results": False,
    },
    "low_yield": {
        "description": "Force the reflection loop.",
        "fail_once_nodes": [],
        "always_fail_nodes": [],
        "force_low_yield": True,
        "force_gap_fill": False,
        "force_no_results": False,
    },
    "gap_fill": {
        "description": "Force the coverage gap-fill path.",
        "fail_once_nodes": [],
        "always_fail_nodes": [],
        "force_low_yield": False,
        "force_gap_fill": True,
        "force_no_results": False,
    },
    "no_results": {
        "description": "Force empty collection results.",
        "fail_once_nodes": [],
        "always_fail_nodes": [],
        "force_low_yield": False,
        "force_gap_fill": False,
        "force_no_results": True,
    },
    "fail_once": {
        "description": "Inject one transient failure into parse and AI BOM nodes.",
        "fail_once_nodes": ["parse_and_standardize", "resolve_ai_bom"],
        "always_fail_nodes": [],
        "force_low_yield": False,
        "force_gap_fill": False,
        "force_no_results": False,
    },
    "always_fail": {
        "description": "Inject a persistent reflection failure.",
        "fail_once_nodes": [],
        "always_fail_nodes": ["reflect_search_strategy"],
        "force_low_yield": False,
        "force_gap_fill": False,
        "force_no_results": False,
    },
}

LIST_ADD_FIELDS: frozenset[str] = frozenset(
    {
        "source_execution_stats",
        "source_health_dashboard",
        "source_drift_alerts",
        "fetch_audits",
        "stored_raw_records",
        "stored_raw_ids",
        "ingest_audits",
        "raw_items",
        "query_telemetry",
        "collection_yield_summary",
        "llm_planning_audits",
        "llm_reflection_audits",
        "llm_standardization_audits",
        "llm_bom_resolution_audits",
        "stix_bundle_refs",
        "llm_dedup_judgments",
        "dedup_decisions",
        "merge_audits",
        "coverage_gaps",
        "gap_fill_dispatch_plans",
        "llm_coverage_analysis_audits",
        "alert_candidates",
        "node_results",
        "errors",
        "completed_nodes",
        "processed_subject_ids",
        "skipped_subject_ids",
    }
)
DICT_MERGE_FIELDS: frozenset[str] = frozenset({"node_attempts", "source_cursors"})

NODE_FOCUS: dict[str, list[str]] = {
    "load_runtime_context": ["run_mode", "run_status", "runtime_context"],
    "supervisor_plan": ["collection_plan", "llm_planning_audits"],
    "dispatch_collection": ["collector_plans", "collection_coordination"],
    "collect_structured_sources": ["raw_items", "fetch_audits", "query_telemetry"],
    "collect_code_sources": ["raw_items", "fetch_audits", "query_telemetry"],
    "collect_paper_sources": ["raw_items", "fetch_audits"],
    "collect_community_sources": ["raw_items", "fetch_audits"],
    "collect_advisory_sources": ["raw_items", "fetch_audits"],
    "store_raw_records": ["stored_raw_ids", "stored_raw_records", "ingest_audits"],
    "assess_collection_yield": [
        "collection_yield_summary",
        "reflection_needed",
        "reflection_rationale",
    ],
    "reflect_search_strategy": [
        "llm_reflection_audits",
        "reflection_round",
        "reflection_needed",
    ],
    "parse_and_standardize": [
        "standardized_items",
        "llm_standardization_audits",
        "processed_count",
    ],
    "semantic_dedup_and_merge": [
        "dedup_decisions",
        "llm_dedup_judgments",
        "dedup_merged_count",
        "stable_attack_records",
        "dedup_persist_summary",
        "dedup_audit_summary",
    ],
    "resolve_ai_bom": [
        "standardized_items",
        "llm_bom_resolution_audits",
        "bom_queue_count",
    ],
    "build_stix_graph": ["standardized_items", "stix_bundle_refs"],
    "score_confidence_and_novelty": ["standardized_items", "new_attack_count"],
    "refresh_coverage_view": ["runtime_context"],
    "coverage_gap_analysis": [
        "coverage_gaps",
        "gap_fill_needed",
        "gap_fill_rationale",
        "gap_fill_round",
    ],
    "generate_alerts": ["alert_candidates"],
    "finalize_run": ["run_status", "finished_at", "errors"],
}


def _merge_state(previous: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(previous)
    for key, value in update.items():
        if key in LIST_ADD_FIELDS and isinstance(merged.get(key), list) and isinstance(value, list):
            merged[key] = merged[key] + value
        elif key in DICT_MERGE_FIELDS and isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _count_or_value(value: Any) -> str:
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return f"{{...{len(value)} keys}}"
    if isinstance(value, str) and len(value) > 120:
        return repr(value[:117] + "...")
    return repr(value)


def _summarize_state(state: dict[str, Any], keys: list[str], verbose: bool) -> list[str]:
    lines: list[str] = []
    for key in keys:
        value = state.get(key)
        if value is None:
            continue
        if verbose:
            formatted = json.dumps(value, indent=2, ensure_ascii=False, default=str)
            lines.append(f"  {key}: {textwrap.indent(formatted, '    ').lstrip()}")
        else:
            lines.append(f"  {key}: {_count_or_value(value)}")
    return lines


def _diff_state(before: dict[str, Any], after: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    changed: dict[str, tuple[Any, Any]] = {}
    for key in set(before) | set(after):
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, list) and isinstance(after_value, list):
            if len(before_value) != len(after_value):
                changed[key] = (before_value, after_value)
        elif before_value != after_value:
            changed[key] = (before_value, after_value)
    return changed


def _build_runtime_context(
    *,
    run_mode: str,
    scenario: str,
    rounds: int,
    live: bool,
) -> RuntimeContextDTO:
    scenario_cfg = SCENARIOS[scenario]
    if live:
        return RuntimeContextDTO.default_live(
            run_mode=run_mode,
            coverage_max_gap_fill_rounds=rounds,
        )

    base_context = RuntimeContextDTO.default_stub(
        run_mode=run_mode,
        fail_once_nodes=scenario_cfg["fail_once_nodes"],
        always_fail_nodes=scenario_cfg["always_fail_nodes"],
        force_low_yield=scenario_cfg["force_low_yield"],
        force_gap_fill=scenario_cfg["force_gap_fill"],
        force_no_results=scenario_cfg["force_no_results"],
        coverage_max_gap_fill_rounds=rounds,
    )
    llm_model = (
        os.getenv("OPENAI_MODEL")
        or os.getenv("OPENAI_FAST_MODEL")
        or base_context.llm_model
    )
    has_llm = bool(os.getenv("OPENAI_API_KEY"))
    llm_strategy = "llm_optional" if has_llm else "rules_only"
    stix_strategy = "llm_optional" if has_llm else "disabled"
    payload = base_context.model_dump(mode="python")
    payload.update(
        {
            "planning_strategy": llm_strategy,
            "reflection_strategy": llm_strategy,
            "standardization_strategy": llm_strategy,
            "dedup_merge_strategy": llm_strategy,
            "dedup_adjudication_strategy": llm_strategy if has_llm else "rules_only",
            "bom_resolution_strategy": llm_strategy,
            "stix_strategy": stix_strategy,
            "coverage_strategy": llm_strategy,
            "llm_model": llm_model,
        }
    )
    return RuntimeContextDTO.model_validate(payload)


class StepDebugger:
    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose
        self.runtime = Phase1GraphRuntime()

    def run(
        self,
        *,
        run_mode: str,
        scenario: str,
        rounds: int,
        live: bool,
    ) -> dict[str, Any]:
        context = _build_runtime_context(
            run_mode=run_mode,
            scenario=scenario,
            rounds=rounds,
            live=live,
        )
        initial_state = build_initial_state(
            run_mode=run_mode,
            runtime_context=context.model_dump(mode="python"),
        )

        print("=== SAADS WP1-1 Debug Runner ===")
        print(f"mode      : {run_mode}")
        print(f"runtime   : {'live' if live else 'stub'}")
        print(f"scenario  : {scenario}")
        print(f"run_id    : {initial_state['run_id']}")
        print(f"trace_id  : {initial_state['trace_id']}")
        print(f"llm_model : {context.llm_model}")
        print(f"bom       : {context.bom_resolution_strategy}")
        print(f"stix      : {context.stix_strategy}")
        print()

        config: Any = {"configurable": {"thread_id": initial_state["run_id"]}}
        previous_state: dict[str, Any] = dict(initial_state)
        node_times: dict[str, float] = {}
        node_sequence: list[str] = []
        total_started = time.perf_counter()

        for chunk in self.runtime.app.stream(initial_state, config=config):
            for node_name, state_update in chunk.items():
                node_started = time.perf_counter()
                merged = _merge_state(previous_state, state_update)
                changed = _diff_state(previous_state, merged)
                node_sequence.append(node_name)

                print(f"[{len(node_sequence):02d}] {node_name}")
                for line in _summarize_state(
                    merged,
                    NODE_FOCUS.get(node_name, []),
                    self.verbose,
                ):
                    print(line)

                extra_keys = [
                    key
                    for key in sorted(changed)
                    if key not in NODE_FOCUS.get(node_name, []) and key != "runtime_context"
                ]
                if extra_keys and not self.verbose:
                    print(f"  changed: {', '.join(extra_keys[:8])}")

                elapsed_ms = (time.perf_counter() - node_started) * 1000.0
                node_times[node_name] = elapsed_ms
                print(f"  elapsed_ms: {elapsed_ms:.1f}")
                print("-" * 72)

                previous_state = merged

        total_elapsed = time.perf_counter() - total_started
        self._print_summary(previous_state, node_sequence, node_times, total_elapsed)
        return previous_state

    def _print_summary(
        self,
        state: dict[str, Any],
        node_sequence: list[str],
        node_times: dict[str, float],
        total_elapsed: float,
    ) -> None:
        print("\n=== Summary ===")
        print(f"run_status        : {state.get('run_status')}")
        print(f"total_elapsed_sec : {total_elapsed:.2f}")
        print(f"raw_items         : {len(state.get('raw_items', []))}")
        print(f"standardized_items: {len(state.get('standardized_items', []))}")
        print(f"stable_records    : {len(state.get('stable_attack_records', []))}")
        print(f"bom_audits        : {len(state.get('llm_bom_resolution_audits', []))}")
        print(f"stix_bundle_refs  : {len(state.get('stix_bundle_refs', []))}")
        print(f"errors            : {len(state.get('errors', []))}")

        bom_resolved = sum(
            1
            for item in state.get("standardized_items", [])
            for resolution in item.get("bom_resolutions", [])
            if resolution.get("resolution_status") == "resolved"
        )
        bom_review_queue = sum(
            1
            for item in state.get("standardized_items", [])
            for resolution in item.get("bom_resolutions", [])
            if resolution.get("resolution_status") != "resolved"
        )
        stix_published = sum(
            1
            for item in state.get("standardized_items", [])
            if item.get("stix_graph_status") == "published"
        )
        print("\nEnrichment")
        print(f"  bom_resolved    : {bom_resolved}")
        print(f"  bom_review_queue: {bom_review_queue}")
        print(f"  stix_published  : {stix_published}")

        if node_sequence:
            print("\nNodes")
            for index, node_name in enumerate(node_sequence, start=1):
                print(
                    f"  [{index:02d}] {node_name:<28} {node_times.get(node_name, 0.0):8.1f} ms"
                )

        if state.get("errors"):
            print("\nErrors")
            for error in state["errors"]:
                if isinstance(error, dict):
                    print(
                        f"  - {error.get('node_name', '?')}: {error.get('message', error)}"
                    )
                else:
                    print(f"  - {error}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP1-1 debug runner")
    parser.add_argument(
        "--mode",
        choices=["bootstrap", "incremental", "gap_fill", "mixed"],
        default="bootstrap",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use RuntimeContextDTO.default_live().",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS.keys()),
        default="normal",
    )
    parser.add_argument("--rounds", type=int, default=1, metavar="N")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--list-scenarios", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--validate-suite",
        choices=[
            "wp11_bugfixes",
            "wp11_persist_robustness",
            "wp11_llm_pool",
            "wp11_enrichment",
        ],
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.list_scenarios:
        print("=== Scenarios ===")
        for name, cfg in SCENARIOS.items():
            print(f"{name:12} {cfg['description']}")
        return

    if args.dry_run:
        context = _build_runtime_context(
            run_mode=args.mode,
            scenario=args.scenario,
            rounds=args.rounds,
            live=args.live,
        )
        print(
            json.dumps(
                context.model_dump(mode="python"),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return

    if args.validate_suite == "wp11_bugfixes":
        from backend.wp11_bugfix_validator import run_wp11_bugfix_suite

        sys.exit(run_wp11_bugfix_suite(verbose=args.verbose))
    if args.validate_suite == "wp11_persist_robustness":
        from backend.wp11_bugfix_validator import run_wp11_persist_robustness_suite

        sys.exit(run_wp11_persist_robustness_suite(verbose=args.verbose))
    if args.validate_suite == "wp11_llm_pool":
        from backend.wp11_bugfix_validator import run_wp11_llm_pool_suite

        sys.exit(run_wp11_llm_pool_suite(verbose=args.verbose))
    if args.validate_suite == "wp11_enrichment":
        from validate_wp11_enrichment import run_validation_suite

        sys.exit(run_validation_suite(verbose=args.verbose))

    debugger = StepDebugger(verbose=args.verbose)
    final_state = debugger.run(
        run_mode=args.mode,
        scenario=args.scenario,
        rounds=args.rounds,
        live=args.live,
    )
    if final_state.get("run_status") in {"failed", "partial_success"}:
        sys.exit(1)


if __name__ == "__main__":
    main()
