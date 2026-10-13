"""Assert remaining acceptance from immutable real-run artifacts, not fixtures."""
from __future__ import annotations

import hashlib
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / ".runtime/community-discovery"
FINAL = LIVE / "remaining-v1-final"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(directory, phase):
    row = read(directory / f"{phase}-round.json")
    data = read(directory / f"{row['run_id']}.json")
    assert not row["failures"], (phase, row["failures"])
    assert all(not item.get("metadata", {}).get("used_stub", False) for item in data["raw_items"])
    assert all(a["strategy_executed"] == "llm_primary" for a in data["standardization_audits"])
    return row, data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    hn_row, hn = run(FINAL, "hn")
    gh_row, gh = run(FINAL, "github")
    neg_row, negative = run(FINAL, "negative")
    reddit_row, reddit = run(LIVE / "reddit-remaining-v1", "reddit")
    state = read(FINAL / "checkpoint.json")
    positive = {"https://news.ycombinator.com/item?id=44250774",
                "https://github.com/SecOpsNews/news/issues/49420",
                "https://github.com/SecOpsNews/news/issues/49449",
                "https://github.com/SecOpsNews/news/issues/49453"}
    nonmatching = {"https://github.com/SecOpsNews/news/issues/51621",
                   "https://github.com/dxpr/ckeditor5-ai-agent/issues/159"}
    records = state["stable_attack_records"]
    target = next(r for r in records if positive <= {o["source_uri"] for o in r["community_observations"]})
    observed = {o["source_uri"] for o in target["community_observations"]}
    assert not observed & nonmatching, "Different-product attacks merged into EchoLeak"
    all_observed = {o["source_uri"] for r in records for o in r["community_observations"]}
    assert nonmatching <= all_observed, "Negative controls were not actually processed"
    assert {"github_issues", "hackernews"} <= set(target["source_coverage"])
    dates = [datetime.fromisoformat(o["published_at"].replace("Z", "+00:00"))
             for o in target["community_observations"] if o.get("published_at")]
    assert datetime.fromisoformat(target["first_seen_at"]) == min(dates)
    assert target["propagation_context"]["basis"] == "observed_publication_chronology_not_causal_propagation"
    artifact_hashes = []
    for observation in target["community_observations"]:
        artifact = Path(observation["artifact_ref"])
        assert artifact.is_file()
        # SourceCollectionCrew pretty-prints JSON on disk. content_hash is the
        # adapter payload hash BEFORE formatting, not the file byte hash.
        # Reconstruct precisely the two verified adapters' json.dumps settings.
        assert observation["source_name"] in {"github_issues", "hackernews"}
        adapter_payload = json.dumps(read(artifact), ensure_ascii=observation["source_name"] == "hackernews")
        assert hashlib.sha256(adapter_payload.encode("utf-8")).hexdigest() == observation["content_hash"]
        artifact_hashes.append({"path": str(artifact.relative_to(ROOT)),
            "file_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "adapter_payload_sha256": observation["content_hash"]})
    resolved = [item for item in gh["dedup_result"]["resolved_items"]
                if item["source_metadata"]["stable_attack_id"] == target["stable_attack_id"]]
    assert any(positive <= {o["source_uri"] for o in item["stix_payload"]["x_saads_community_observations"]}
               for item in resolved), "STIX lost provenance"
    assert any(positive <= {ref.get("url") for ref in item["stix_payload"].get("external_references", [])}
               for item in resolved), "STIX external references lost source URLs"

    before = read(FINAL / "hn-before.json")["source_cursors"]["_community"]
    learned = read(FINAL / "hn-after.json")["source_cursors"]["_community"]
    added = set(learned["keywords"]) - set(before["keywords"])
    assert added
    assert read(FINAL / "github-config.json")["dynamic_queries"] is True
    dynamic_evidence = []
    for item in gh["raw_items"]:
        metadata = item["metadata"]
        gate = metadata["community_filter"]
        query = metadata["query_text"]
        for term in added:
            if query.startswith('"' + term + '" ') and term in gate["stage1_matches"] and gate["stage2_status"] == "succeeded":
                proof = learned["keyword_evidence"][term]
                assert proof["model"] == "deepseek-flash"
                assert Path(proof["artifact_ref"]).is_file()
                dynamic_evidence.append({"term": term, "learned_from": proof,
                    "subsequent_query": query, "subsequent_source_uri": item["source_uri"],
                    "score": gate["score"], "keep": gate["keep"]})
    assert dynamic_evidence, "No learned keyword actually reached a subsequent live query and LLM gate"
    previous = read(LIVE / "deepseek-live/community-v1-499495e35793.json")
    gates = [item["metadata"]["community_filter"] for item in previous["raw_items"]]
    keyword_reject = sum(g["stage2_status"] == "not_needed" and not g["keep"] for g in gates)
    llm_reject = sum(g["stage2_status"] == "succeeded" and not g["keep"] for g in gates)
    assert keyword_reject and llm_reject
    assert reddit_row["filtered_retained_count"] > 0
    platforms = read(LIVE / "remaining-v1/platforms.json")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reddit": {"status": "PASS", "mode": "public RSS, not authenticated/private Reddit API",
                   "run": reddit_row["run_id"], "raw": reddit_row["raw_count"],
                   "retained": reddit_row["filtered_retained_count"],
                   "source_uris": reddit_row["source_uris"]},
        "discord": platforms["discord"], "twitter": platforms["twitter"],
        "cross_platform": {"status": "PASS", "runs": [hn_row["run_id"], gh_row["run_id"], neg_row["run_id"]],
                           "stable_attack_id": target["stable_attack_id"],
                           "positive_sources": sorted(positive), "negative_sources_not_merged": sorted(nonmatching),
                           "first_seen_at": target["first_seen_at"],
                           "propagation_context": target["propagation_context"],
                           "adapter_payload_hashes_verified": True, "artifact_hashes": artifact_hashes,
                           "stix_provenance_verified": True},
        "dynamic_keywords_two_stage": {"status": "PASS", "evidence": dynamic_evidence,
                                       "prior_live_keyword_rejections": keyword_reject,
                                       "prior_live_llm_rejections": llm_reject,
                                       "prior_live_run": "community-v1-499495e35793"},
    }
    (FINAL / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.freeze:
        # Freeze the actual working files, never tag an unrelated pre-change HEAD.
        # Explicit roots exclude .env, databases, dependencies and private runtime.
        files = []
        for folder in ("backend/agents/intel_agents", "backend/api", "frontend/app", "frontend/src", "frontend/components"):
            path = ROOT / folder
            if path.exists():
                files.extend(p for p in path.rglob("*") if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".css", ".json"} and "__pycache__" not in p.parts)
        for name in (".env.example", "wp11_llm_profiles.json", "wp11_llm_route_presets.json",
                     "community_discovery.example.json", "pyproject.toml", "frontend/package.json",
                     "frontend/package-lock.json", "scripts/run_community_v1_monitor.py",
                     "scripts/verify_community_remaining_live.py", "scripts/summarize_community_remaining.py"):
            if (ROOT / name).is_file():
                files.append(ROOT / name)
        hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(set(files))}
        manifest = {
            "status": "FROZEN_LOCAL_SOURCE_SNAPSHOT",
            "frozen_at": report["generated_at"],
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "git_tag_created": False,
            "suggested_tag_after_reviewed_commit": "saads-community-v1-20260915",
            "scope": "Community discovery only; preserves existing API/frontend. No KG, WP1-2, migration or attack execution.",
            "passed_remaining": ["Reddit public RSS with real LLM/STIX", "cross-platform semantic association with provenance", "dynamic keywords and two-stage filtering"],
            "blocked_excluded_from_enabled_sources": ["Discord authorized bot/channel access", "X authorized search API"],
            "evidence": str((FINAL / "acceptance.json").relative_to(ROOT)).replace("\\", "/"),
            "evidence_sha256": hashlib.sha256((FINAL / "acceptance.json").read_bytes()).hexdigest(),
            "source_sha256": hashes,
            "notes": "No commit or tag was created because the worktree contains pre-existing unrelated changes. .env and secrets are excluded.",
        }
        (ROOT / "docs/community_v1_freeze.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value["status"] for key, value in report.items() if isinstance(value, dict)}))


if __name__ == "__main__":
    main()
