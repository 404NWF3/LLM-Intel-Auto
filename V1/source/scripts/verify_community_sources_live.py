"""Read-only upstream acceptance probes through the real SAADS collection chain."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from backend.agents.intel_agents.crews.source_collection_crew import SourceCollectionCrew
from backend.agents.intel_agents.agents.standardizer_agent import StandardizerAgent
from backend.agents.intel_agents.schemas.intel import RawCollectedItemDTO, StandardizedIntelDTO


def main():
    root = ROOT / ".runtime/community-discovery" / ("probe-" + uuid4().hex[:10])
    root.mkdir(parents=True)
    config = json.loads((ROOT / "community_discovery.example.json").read_text(encoding="utf-8"))
    config["source_plans"].append({**config["source_plans"][1], "source_name": "reddit"})
    state = {}
    results = []
    for round_index in range(2):
        result = SourceCollectionCrew().collect(
            config["source_plans"], trace_id=f"live-{round_index}", run_mode="incremental",
            reflection_round=0, runtime_mode="live", retry_attempts=2,
            request_timeout_seconds=25, artifact_store_dir=str(root / "artifacts"),
            source_registry_overrides=config["source_registry_overrides"], source_cursors=state,
            max_parallel_sources=3, prefer_db_source_registry=False)
        for item in result["raw_items"]:
            RawCollectedItemDTO.model_validate(item)
        standardized, audits = StandardizerAgent(strategy="rules_only").standardize_batch(result["raw_items"])
        for item in standardized:
            StandardizedIntelDTO.model_validate(item)
            assert item["stix_payload"]["type"] == "attack-pattern"
        results.append({"round": round_index, "collection": result, "standardized": standardized,
                        "standardization_audits": audits, "cursor_in": state})
        state = result["source_cursors"]
        (root / f"round-{round_index}.json").write_text(json.dumps(results[-1], indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"round": round_index, "stats": result["source_execution_stats"],
                          "raw": len(result["raw_items"]), "structured": len(standardized)}, ensure_ascii=True), flush=True)
    # Force a real upstream timeout. Successful cursors must remain unchanged.
    failed = SourceCollectionCrew().collect(
        [config["source_plans"][1]], trace_id="real-timeout", run_mode="incremental",
        reflection_round=0, runtime_mode="live", retry_attempts=2,
        request_timeout_seconds=0.000001, artifact_store_dir=str(root / "artifacts"),
        source_cursors=state, max_parallel_sources=1, prefer_db_source_registry=False)
    assert all(not stat["success"] and not stat["used_stub"] for stat in failed["source_execution_stats"])
    assert failed["source_cursors"] == state, "Failed request corrupted checkpoints"
    (root / "failure-recovery.json").write_text(json.dumps(failed, indent=2), encoding="utf-8")
    recovered = SourceCollectionCrew().collect(
        [config["source_plans"][1]], trace_id="after-timeout", run_mode="incremental",
        reflection_round=0, runtime_mode="live", retry_attempts=2,
        request_timeout_seconds=25, artifact_store_dir=str(root / "artifacts"),
        source_cursors=failed["source_cursors"], max_parallel_sources=1,
        prefer_db_source_registry=False)
    assert all(stat["success"] and not stat["used_stub"] for stat in recovered["source_execution_stats"])
    (root / "resumed.json").write_text(json.dumps(recovered, indent=2), encoding="utf-8")
    overlaps = {}
    for name in ("github_issues", "hackernews", "discourse"):
        before = {item["external_id"] for item in results[0]["collection"]["raw_items"] if item["source_name"] == name}
        after = {item["external_id"] for item in results[1]["collection"]["raw_items"] if item["source_name"] == name}
        overlaps[name] = {"round1": len(before), "round2": len(after), "overlap": len(before & after)}
    (root / "summary.json").write_text(json.dumps({"source_rounds": overlaps,
        "failure_checkpoint_preserved": True, "resume_success": True,
        "llm_filter_validated": False, "semantic_dedup_validated": False}, indent=2), encoding="utf-8")
    print(json.dumps({"source_rounds": overlaps, "resume_success": True}), flush=True)
    print(json.dumps({"failure_checkpoint_preserved": True, "evidence_dir": str(root)}), flush=True)


if __name__ == "__main__":
    main()
