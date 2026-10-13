"""Run SAADS Community V1 live incremental collection on a fixed interval.

This is an operations runner, not a second collection implementation.  Each
round delegates to the existing live SourceCollectionCrew, StandardizerAgent,
and DedupMergeAgent, and persists only their cursor/checkpoint and stable
deduplication state so an interrupted 24-hour watch can continue safely.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.intel_agents.agents.dedup_merge_agent import DedupMergeAgent
from backend.agents.intel_agents.agents.standardizer_agent import StandardizerAgent
from backend.agents.intel_agents.crews.source_collection_crew import SourceCollectionCrew


DEFAULT_ROOT = Path(".runtime/community-v1/monitor")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _plans() -> list[dict[str, Any]]:
    return [
        {
            "source_name": "hackernews",
            "source_type": "community",
            "priority": 1.0,
            "queries": ["AI security vulnerability"],
            "query_intent": "evidence_corroboration",
            "query_provenance": "community_v1_two_hour_incremental_monitor",
            "max_results": 10,
            "fetch_mode": "incremental",
            "time_window_days": 7,
        }
    ]


def run_round(state: dict[str, Any], root: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    runtime_config = config.get("runtime_config", {})
    plans = deepcopy(config.get("source_plans") or _plans())
    if config.get("dynamic_queries"):
        learned = state.get("source_cursors", {}).get("_community", {}).get("keywords", [])[-3:]
        for plan in plans:
            additions = learned
            if plan["source_name"] == "github_issues":
                # Learned text must not discard the configured repository scope
                # or become GitHub search operators.
                additions = []
                for original in plan["queries"]:
                    scope = " ".join(re.findall(r"\b(?:repo|org|user):[^\s]+", original))
                    for term in learned:
                        quoted = term.replace('"', '').replace('\\', '')
                        additions.append(f'"{quoted}" {scope}'.strip())
            plan["queries"] = list(dict.fromkeys([*plan["queries"], *additions]))
    started_at = _now()
    started = time.perf_counter()
    run_id = f"community-v1-{uuid4().hex[:12]}"
    trace_id = f"community-v1-monitor-{uuid4().hex[:12]}"
    collection = SourceCollectionCrew().collect(
        plans,
        trace_id=trace_id,
        run_mode="incremental",
        reflection_round=0,
        runtime_mode="live",
        retry_attempts=2,
        request_timeout_seconds=30.0,
        artifact_store_dir=str(root / "raw"),
        source_registry_overrides=config.get("source_registry_overrides") or [
            {
                "source_name": "hackernews",
                "source_type": "community",
                "enabled": True,
                "default_max_results": 10,
                "default_time_window_days": 7,
            }
        ],
        source_cursors=state.get("source_cursors") or {},
        max_parallel_sources=3,
        prefer_db_source_registry=False,
        llm_runtime_config=runtime_config,
    )
    raw_items = collection["raw_items"]
    standardized, standardization_audits = StandardizerAgent(
        strategy=config.get("standardization_strategy", "rules_only"),
        llm_runtime_config=runtime_config, standardization_max_concurrency=2
    ).standardize_batch(raw_items)
    dedup_result, judgments = DedupMergeAgent(
        strategy=config.get("dedup_merge_strategy", "rules_only"),
        llm_runtime_config=runtime_config,
    ).dedup_and_merge(
        standardized,
        existing_records=state.get("stable_attack_records") or [],
    )
    stats = collection["source_execution_stats"]
    failed = [
        {
            "source": row["source_name"],
            "error_type": row.get("error_type"),
            "error_message": row.get("error_message"),
            "attempt_count": row["attempt_count"],
        }
        for row in stats
        if not row["success"]
    ]
    row = {
        "run_id": run_id,
        "trace_id": trace_id,
        "started_at": started_at,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "source_stats": stats,
        "source_cursors": collection["source_cursors"],
        "raw_count": len(raw_items),
        "filtered_retained_count": len(standardized),
        "new_count": dedup_result["new_attack_count"],
        "merged_count": dedup_result["dedup_merged_count"],
        "relevance_scores": [item.get("relevance_score") for item in raw_items],
        "sources": sorted({item["source_name"] for item in raw_items}),
        "source_uris": [item["source_uri"] for item in raw_items],
        "artifact_refs": [item["artifact_ref"] for item in raw_items],
        "standardization_strategies": sorted(
            {audit["strategy_executed"] for audit in standardization_audits}
        ),
        "failures": failed,
    }
    _write_json(root / f"{run_id}.json", {
        "raw_items": raw_items, "standardized_items": standardized,
        "standardization_audits": standardization_audits,
        "dedup_result": dedup_result, "llm_dedup_judgments": judgments,
        "fetch_audits": collection["fetch_audits"],
    })
    state["source_cursors"] = collection["source_cursors"]
    state["stable_attack_records"] = dedup_result["stable_attack_records"]
    state["completed_rounds"] = int(state.get("completed_rounds", 0)) + 1
    state["updated_at"] = _now()
    return row


def write_report(log_path: Path, report_path: Path, state: dict[str, Any]) -> None:
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    totals = {
        "rounds": len(rows),
        "raw": sum(int(row["raw_count"]) for row in rows),
        "retained": sum(int(row["filtered_retained_count"]) for row in rows),
        "new": sum(int(row["new_count"]) for row in rows),
        "merged": sum(int(row["merged_count"]) for row in rows),
        "failures": sum(len(row["failures"]) for row in rows),
    }
    relevance_scores = [
        float(score)
        for row in rows
        for score in row.get("relevance_scores", [])
        if score is not None
    ]
    lines = [
        "# SAADS Community V1 24h Monitor Report",
        "",
        f"Updated (UTC): {state.get('updated_at', _now())}",
        f"Rounds: {totals['rounds']}",
        f"Raw collected: {totals['raw']}",
        f"Filtered/structured retained: {totals['retained']}",
        f"New: {totals['new']}",
        f"Merged: {totals['merged']}",
        f"Failed source runs: {totals['failures']}",
        (
            "Relevance scores (min/avg/max): "
            f"{min(relevance_scores):.3f}/{sum(relevance_scores) / len(relevance_scores):.3f}/"
            f"{max(relevance_scores):.3f}"
            if relevance_scores
            else "Relevance scores (min/avg/max): none"
        ),
        "",
        "| started_at (UTC) | sources | raw | retained | new | merged | relevance scores | retries/failures | duration_s | cursors |",
        "|---|---|---:|---:|---:|---:|---|---|---:|---|",
    ]
    for row in rows:
        retry = ", ".join(
            f"{item['source']}:{item['attempt_count']}:{item['error_type']}"
            for item in row["failures"]
        ) or "none"
        cursors = json.dumps(row["source_cursors"], ensure_ascii=False, separators=(",", ":"))
        scores = ", ".join(f"{float(score):.3f}" for score in row.get("relevance_scores", []) if score is not None) or "none"
        lines.append(
            f"| {row['started_at']} | {', '.join(row['sources']) or 'none'} | "
            f"{row['raw_count']} | {row['filtered_retained_count']} | {row['new_count']} | "
            f"{row['merged_count']} | {scores} | {retry} | {row['duration_seconds']} | `{cursors}` |"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--interval-seconds", type=int, default=7200)
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--config", type=Path, help="Source plans, registry overrides and runtime settings (no secrets)")
    args = parser.parse_args()
    if args.interval_seconds <= 0 or args.duration_hours <= 0:
        raise SystemExit("interval-seconds and duration-hours must be positive")

    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "checkpoint.json"
    log_path = root / "rounds.jsonl"
    report_path = root / "24h_report.md"
    state = _read_json(state_path, {"source_cursors": {}, "stable_attack_records": []})
    config = _read_json(args.config, {}) if args.config else {}
    deadline = time.monotonic() + (0 if args.once else args.duration_hours * 3600)
    had_failures = False
    while True:
        round_started_at = _now()
        round_started = time.perf_counter()
        try:
            row = run_round(state, root, config)
        except Exception as exc:
            row = {
                "run_id": f"community-v1-{uuid4().hex[:12]}",
                "trace_id": None,
                "started_at": round_started_at,
                "duration_seconds": round(time.perf_counter() - round_started, 3),
                "source_stats": [],
                "source_cursors": state.get("source_cursors", {}),
                "raw_count": 0,
                "filtered_retained_count": 0,
                "new_count": 0,
                "merged_count": 0,
                "relevance_scores": [],
                "sources": [],
                "source_uris": [],
                "artifact_refs": [],
                "standardization_strategies": [],
                "failures": [{"source": "monitor", "error_type": type(exc).__name__, "error_message": str(exc), "attempt_count": 1}],
            }
            state["updated_at"] = _now()
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        _write_json(state_path, state)
        write_report(log_path, report_path, state)
        print(json.dumps({key: row[key] for key in ("run_id", "raw_count", "filtered_retained_count", "new_count", "merged_count", "duration_seconds", "failures")}, ensure_ascii=False), flush=True)
        had_failures = had_failures or bool(row["failures"])
        if args.once or time.monotonic() + args.interval_seconds > deadline:
            break
        time.sleep(args.interval_seconds)
    return 1 if had_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
