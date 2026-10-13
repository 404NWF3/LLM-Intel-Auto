"""Remaining Community V1 acceptance using real APIs and existing pipelines only."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
from run_community_v1_monitor import run_round, _write_json


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["hn", "github", "negative", "reddit", "platforms"], required=True)
    parser.add_argument("--root", type=Path, default=ROOT / ".runtime/community-discovery/remaining-v1")
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.phase == "platforms":
        from backend.agents.intel_agents.crews.source_collection_crew import SourceCollectionCrew
        checked_at = datetime.now(timezone.utc).isoformat()
        # Do not fabricate authentication requests with invented credentials.
        report = {
            "checked_at": checked_at,
            "discord": {"status": "BLOCKED", "credential_configured": bool(os.getenv("DISCORD_BOT_TOKEN")),
                        "requires": ["DISCORD_BOT_TOKEN", "source.default_params.guild_id", "source.default_params.channel_id"],
                        "reason": "No authorized bot/channel configuration is present; no private messages requested."},
            "twitter": {"status": "BLOCKED", "credential_configured": bool(os.getenv("TWITTER_BEARER_TOKEN")),
                        "requires": ["TWITTER_BEARER_TOKEN", "X recent-search API access"],
                        "reason": "No API bearer credential is present."},
        }
        collected = SourceCollectionCrew().collect(
            [{"source_name": "reddit", "source_type": "community", "priority": 1.0,
              "queries": ["prompt injection"], "query_intent": "broad_recall",
              "query_provenance": "remaining_platform_acceptance",
              "max_results": 3, "fetch_mode": "incremental", "time_window_days": 730}],
            trace_id="remaining-reddit-live", run_mode="incremental", reflection_round=0,
            runtime_mode="live", retry_attempts=2, request_timeout_seconds=20,
            artifact_store_dir=str(root / "platform-raw"), prefer_db_source_registry=False)
        report["reddit"] = {
            "status": "PASS" if collected["raw_items"] else "BLOCKED",
            "adapter": "existing public Reddit RSS", "raw_count": len(collected["raw_items"]),
            "source_stats": collected["source_execution_stats"],
            "reason": "Authenticated Reddit API access is not configured; public RSS was tested directly.",
        }
        _write_json(root / "platforms.json", report)
        print(json.dumps(report), flush=True)
        return 0
    checkpoint = root / "checkpoint.json"
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
    else:
        original = json.loads((ROOT / ".runtime/community-discovery/deepseek-live/checkpoint.json").read_text(encoding="utf-8"))
        state = {"source_cursors": {"_community": deepcopy(original["source_cursors"]["_community"])},
                 "stable_attack_records": []}
        _write_json(root / "seed.json", state)
    before = deepcopy(state)
    queries = {
        "hn": ("hackernews", "EchoLeak"),
        "github": ("github_issues", "EchoLeak repo:SecOpsNews/news"),
        "negative": ("github_issues", "EchoLeak repo:dxpr/ckeditor5-ai-agent"),
        "reddit": ("reddit", "prompt injection"),
    }
    source, query = queries[args.phase]
    config = {
        "dynamic_queries": args.phase == "github",
        "runtime_config": {"community_filter_enabled": True, "llm_retry_attempts": 3},
        "standardization_strategy": "llm_required", "dedup_merge_strategy": "llm_required",
        "source_registry_overrides": [{"source_name": source, "enabled": True}],
        "source_plans": [{"source_name": source, "source_type": "community", "priority": 1.0,
                          "queries": [query], "query_intent": "broad_recall",
                          "query_provenance": "remaining_cross_platform_acceptance",
                          "max_results": 5, "fetch_mode": "incremental", "time_window_days": 730}],
    }
    _write_json(root / f"{args.phase}-config.json", config)
    _write_json(root / f"{args.phase}-before.json", before)
    try:
        row = run_round(state, root, config)
    except Exception as exc:
        _write_json(root / f"{args.phase}-failure.json", {
            "at": datetime.now(timezone.utc).isoformat(), "error_type": type(exc).__name__,
            "checkpoint_committed": False, "source_cursors_unchanged": state["source_cursors"] == before["source_cursors"],
        })
        raise
    _write_json(root / f"{args.phase}-round.json", row)
    _write_json(checkpoint, state)
    _write_json(root / f"{args.phase}-after.json", state)
    print(json.dumps({k: row[k] for k in ("run_id", "raw_count", "filtered_retained_count", "new_count", "merged_count", "failures", "duration_seconds")}), flush=True)
    return 1 if row["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
