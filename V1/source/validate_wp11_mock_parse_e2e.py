from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

load_dotenv(ROOT / ".env", override=False)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.agents.intel_agents.orchestrator.nodes import (
    build_stix_graph_node,
    parse_and_standardize_node,
    resolve_ai_bom_node,
    semantic_dedup_and_merge_node,
)
from backend.agents.intel_agents.orchestrator.state import build_initial_state
from backend.agents.intel_agents.schemas.runtime import RuntimeContextDTO
from backend.agents.intel_agents.services.raw_ingest_flow import RawIngestFlow
from backend.db.typing import SqlContext
from backend.db.unit_of_work import UnitOfWork


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    details: str


def _print(title: str, value: Any | None = None) -> None:
    if value is None:
        print(title, flush=True)
        return
    print(f"{title}{value}", flush=True)


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    description = getattr(cursor, "description", None) or []
    columns: list[str] = []
    for col in description:
        if hasattr(col, "name"):
            columns.append(str(col.name))
        elif isinstance(col, (tuple, list)) and col:
            columns.append(str(col[0]))
        else:
            columns.append(str(col))
    return dict(zip(columns, row))


def _mock_payload_text() -> str:
    return (
        "Security Advisory: Indirect Prompt Injection in LangChain Agents Using "
        "OpenAI Agents SDK\n\n"
        "Researchers identified an indirect prompt injection issue in a "
        "retrieval-augmented agent built with LangChain and the OpenAI Agents SDK. "
        "A malicious knowledge-base document can place hidden instructions into "
        "the agent context. Once retrieved, the LangChain agent forwards those "
        "instructions into a tool-enabled execution step, causing the OpenAI "
        "Agents SDK runtime to invoke an unauthorized outbound request and leak "
        "internal reasoning notes. Affected deployments were running LangChain "
        "versions before 0.2.14 and OpenAI Agents SDK versions before 0.1.1. "
        "The issue maps to OWASP LLM01 Prompt Injection and CWE-20 Improper "
        "Input Validation. Internal severity assessment: High. Estimated CVSS 8.6. "
        "Researchers tracked the issue as CVE-2026-42424. Recommended mitigation "
        "includes retrieval isolation, tool confirmation, outbound allowlists, "
        "and upgrading LangChain and the OpenAI Agents SDK."
    )


def _build_raw_item(*, run_tag: str, payload_path: Path) -> dict[str, Any]:
    payload_text = payload_path.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "query_run_id": f"query_{uuid4().hex[:10]}",
        "source_name": "github_advisories",
        "source_uri": f"https://example.test/github_advisories/{run_tag}",
        "external_id": f"MOCK-{run_tag}",
        "title": "Indirect Prompt Injection in LangChain Agents Using OpenAI Agents SDK",
        "summary": (
            "Indirect prompt injection in a LangChain agent using the OpenAI "
            "Agents SDK enables unauthorized tool execution and data leakage."
        ),
        "author": "WP11 E2E Probe",
        "published_at": now,
        "fetched_at": now,
        "raw_format": "text",
        "artifact_ref": payload_path.as_posix(),
        "payload_uri": payload_path.as_posix(),
        "language_code": "en",
        "relevance_score": 0.99,
        "parser_status": "pending",
        "metadata": {
            "query_text": "langchain openai agents sdk prompt injection advisory",
            "severity": "high",
        },
        "content_hash": sha256(payload_text.encode("utf-8")).hexdigest(),
    }


def _build_runtime_context(runtime_dir: Path) -> RuntimeContextDTO:
    base = RuntimeContextDTO.default_stub(run_mode="bootstrap")
    payload = base.model_dump(mode="python")
    payload.update(
        {
            "source_runtime_mode": "stub",
            "planning_strategy": "rules_only",
            "reflection_strategy": "rules_only",
            "coverage_strategy": "rules_only",
            "standardization_strategy": "llm_required",
            "bom_resolution_strategy": "llm_required",
            "stix_strategy": "llm_required",
            "dedup_merge_strategy": "rules_only",
            "dedup_adjudication_strategy": "rules_only",
            "artifact_store_dir": (runtime_dir / "raw_records").as_posix(),
            "audit_store_dir": (runtime_dir / "audit").as_posix(),
            "dedup_store_dir": (runtime_dir / "dedup").as_posix(),
            "qdrant_local_path": (runtime_dir / "vector_memory").as_posix(),
            "persist_raw_records_to_db": True,
            "validate_llm_online": False,
            "llm_retry_attempts": 2,
            "llm_backoff_base_seconds": 1.0,
            "llm_backoff_max_seconds": 6.0,
            "standardization_max_concurrency": 1,
        }
    )
    return RuntimeContextDTO.model_validate(payload)


def _find_attack_by_raw_id(raw_id: str) -> dict[str, Any] | None:
    sql = """
    SELECT
        ae.attack_id,
        a.attack_code,
        a.canonical_name,
        a.attack_family,
        a.severity_level,
        a.stix_graph_status,
        a.stix_type,
        a.stix_payload
    FROM wp11.attack_evidence ae
    JOIN wp11.attack_entry a
      ON a.attack_id = ae.attack_id
    WHERE ae.raw_id = %(raw_id)s
    ORDER BY ae.extracted_at DESC
    LIMIT 1
    """
    with UnitOfWork(
        context=SqlContext(trace_id=f"probe_lookup_{uuid4().hex[:8]}", agent_name="wp11_mock_e2e_lookup")
    ) as uow:
        cursor = uow.conn.execute(sql, {"raw_id": raw_id})
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


def _db_snapshot(attack_id: str) -> dict[str, Any]:
    with UnitOfWork(
        context=SqlContext(trace_id=f"probe_verify_{uuid4().hex[:8]}", agent_name="wp11_mock_e2e_verify")
    ) as uow:
        attack = uow.attacks.get_attack_by_id(attack_id)
        taxonomy = uow.attacks.list_taxonomy_maps(attack_id)
        cvss = uow.attacks.list_cvss_assessments(attack_id)
        mentions = uow.components.list_component_mentions_by_attack(attack_id)
        impacts = uow.components.list_component_impacts_by_attack(attack_id)
        bundles = uow.stix.list_bundles_by_attack(attack_id)

        stix_audit_sql = """
        SELECT audit_id, review_decision, graph_confidence, reasoning_summary, created_at
        FROM wp11.stix_extraction_audit
        WHERE attack_id = %(attack_id)s
        ORDER BY created_at DESC
        """
        bom_audit_sql = """
        SELECT audit_id, mention_id, strategy_executed, llm_decision, selected_component_code, created_at
        FROM wp11.bom_resolution_audit
        WHERE attack_id = %(attack_id)s
        ORDER BY created_at DESC
        """
        stix_queue_sql = """
        SELECT review_id, reason_code, queue_status, created_at
        FROM wp11.stix_review_queue
        WHERE attack_id = %(attack_id)s
        ORDER BY created_at DESC
        """

        stix_audit_cursor = uow.conn.execute(stix_audit_sql, {"attack_id": attack_id})
        stix_audits = [_row_to_dict(stix_audit_cursor, row) for row in stix_audit_cursor.fetchall()]
        bom_audit_cursor = uow.conn.execute(bom_audit_sql, {"attack_id": attack_id})
        bom_audits = [_row_to_dict(bom_audit_cursor, row) for row in bom_audit_cursor.fetchall()]
        stix_queue_cursor = uow.conn.execute(stix_queue_sql, {"attack_id": attack_id})
        stix_queue = [_row_to_dict(stix_queue_cursor, row) for row in stix_queue_cursor.fetchall()]

        return {
            "attack": attack,
            "taxonomy": taxonomy,
            "cvss": cvss,
            "mentions": mentions,
            "impacts": impacts,
            "bundles": bundles,
            "stix_audits": stix_audits,
            "bom_audits": bom_audits,
            "stix_queue": stix_queue,
        }


def _run_chain(*, verbose: bool) -> tuple[dict[str, Any], dict[str, Any], list[CheckResult]]:
    run_tag = f"wp11e2e_{uuid4().hex[:10]}"
    runtime_dir = ROOT / ".runtime" / "wp11" / "mock_parse_e2e" / run_tag
    payload_dir = runtime_dir / "payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_path = payload_dir / "mock_attack_intel.txt"
    payload_path.write_text(_mock_payload_text(), encoding="utf-8")

    raw_item = _build_raw_item(run_tag=run_tag, payload_path=payload_path)
    trace_id = f"trace_{uuid4().hex[:12]}"

    _print("[1/6] ingest raw intelligence")
    ingest = RawIngestFlow(
        artifact_store_dir=(runtime_dir / "raw_records").as_posix(),
        audit_store_dir=(runtime_dir / "audit").as_posix(),
    )
    stored_records, ingest_audits = ingest.ingest(
        [raw_item],
        run_id=run_tag,
        trace_id=trace_id,
        persist_to_db=True,
        created_by="wp11_mock_parse_e2e",
    )
    _print("  stored_records=", len(stored_records))
    if not stored_records:
        return {}, {}, [CheckResult("raw_ingest_db", False, "RawIngestFlow did not persist the mock raw record to DB.")]

    raw_id = str(stored_records[0]["raw_id"])
    _print("  raw_id=", raw_id)

    _print("[2/6] build parse-chain state")
    runtime_context = _build_runtime_context(runtime_dir)
    state = build_initial_state(
        run_mode="bootstrap",
        runtime_context=runtime_context.model_dump(mode="python"),
    )
    state["trace_id"] = trace_id
    state["raw_items"] = [raw_item]
    state["stored_raw_records"] = stored_records
    state["stored_raw_ids"] = [raw_id]
    state["ingest_audits"] = ingest_audits

    _print("[3/6] parse_and_standardize")
    state.update(parse_and_standardize_node(state))
    standardized_items = state.get("standardized_items", [])
    _print("  standardized_items=", len(standardized_items))
    if standardized_items and verbose:
        print(json.dumps(standardized_items[0], ensure_ascii=False, indent=2, default=str), flush=True)

    _print("[4/6] semantic_dedup_and_merge")
    state.update(semantic_dedup_and_merge_node(state))
    _print("  stable_attack_records=", len(state.get("stable_attack_records", [])))
    _print("  dedup_decisions=", len(state.get("dedup_decisions", [])))

    _print("[5/6] resolve_ai_bom")
    state.update(resolve_ai_bom_node(state))
    item_after_bom = (state.get("standardized_items") or [{}])[0]
    bom_resolutions = item_after_bom.get("bom_resolutions", [])
    _print("  bom_resolutions=", len(bom_resolutions))
    _print("  llm_bom_resolution_audits=", len(state.get("llm_bom_resolution_audits", [])))
    if bom_resolutions and verbose:
        print(json.dumps(bom_resolutions, ensure_ascii=False, indent=2, default=str), flush=True)

    _print("[6/6] build_stix_graph")
    state.update(build_stix_graph_node(state))
    _print("  stix_bundle_refs=", len(state.get("stix_bundle_refs", [])))
    _print("  errors=", len(state.get("errors", [])))

    attack_row = _find_attack_by_raw_id(raw_id)
    db_snapshot: dict[str, Any] = {}
    if attack_row is not None:
        db_snapshot = _db_snapshot(str(attack_row["attack_id"]))

    checks: list[CheckResult] = []
    first_item = standardized_items[0] if standardized_items else {}
    checks.append(
        CheckResult(
            "raw_ingest_db",
            bool(stored_records),
            f"raw_id={raw_id}",
        )
    )
    checks.append(
        CheckResult(
            "phase3_bom_mentions",
            bool(first_item.get("bom_mentions")),
            f"bom_mentions={len(first_item.get('bom_mentions', []))}",
        )
    )
    checks.append(
        CheckResult(
            "phase3_initial_stix_payload",
            bool(first_item.get("stix_payload")),
            f"stix_type={first_item.get('stix_type')}",
        )
    )
    checks.append(
        CheckResult(
            "dedup_attack_persisted",
            attack_row is not None,
            (
                f"attack_code={attack_row['attack_code']} canonical_name={attack_row['canonical_name']}"
                if attack_row
                else "attack_evidence -> attack_entry lookup returned no row"
            ),
        )
    )
    checks.append(
        CheckResult(
            "taxonomy_persisted",
            bool(db_snapshot.get("taxonomy")),
            f"taxonomy_rows={len(db_snapshot.get('taxonomy', []))}",
        )
    )
    checks.append(
        CheckResult(
            "cvss_persisted",
            bool(db_snapshot.get("cvss")),
            f"cvss_rows={len(db_snapshot.get('cvss', []))}",
        )
    )
    checks.append(
        CheckResult(
            "ai_bom_persisted",
            bool(db_snapshot.get("mentions")) or bool(db_snapshot.get("impacts")),
            (
                f"mention_rows={len(db_snapshot.get('mentions', []))} "
                f"impact_rows={len(db_snapshot.get('impacts', []))}"
            ),
        )
    )
    checks.append(
        CheckResult(
            "stix_persisted",
            bool(db_snapshot.get("bundles")),
            (
                f"bundle_rows={len(db_snapshot.get('bundles', []))} "
                f"state_errors={len(state.get('errors', []))}"
            ),
        )
    )

    return state, db_snapshot, checks


def run_probe(*, verbose: bool = False) -> int:
    state, db_snapshot, checks = _run_chain(verbose=verbose)

    print("\n=== Check Results ===", flush=True)
    passed = 0
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.details}", flush=True)
        if check.ok:
            passed += 1

    print("\n=== Runtime Summary ===", flush=True)
    if state:
        print(f"standardized_items={len(state.get('standardized_items', []))}", flush=True)
        print(f"dedup_decisions={len(state.get('dedup_decisions', []))}", flush=True)
        print(f"llm_bom_resolution_audits={len(state.get('llm_bom_resolution_audits', []))}", flush=True)
        print(f"stix_bundle_refs={len(state.get('stix_bundle_refs', []))}", flush=True)
        print(f"errors={len(state.get('errors', []))}", flush=True)
        if state.get("errors"):
            print("last_error=", flush=True)
            print(json.dumps(state["errors"][-1], ensure_ascii=False, indent=2, default=str), flush=True)

    print("\n=== DB Summary ===", flush=True)
    attack = db_snapshot.get("attack")
    if attack is not None:
        print(f"attack_code={attack.attack_code}", flush=True)
        print(f"canonical_name={attack.canonical_name}", flush=True)
        print(f"stix_graph_status={attack.stix_graph_status}", flush=True)
        print(f"taxonomy_rows={len(db_snapshot.get('taxonomy', []))}", flush=True)
        print(f"cvss_rows={len(db_snapshot.get('cvss', []))}", flush=True)
        print(f"mention_rows={len(db_snapshot.get('mentions', []))}", flush=True)
        print(f"impact_rows={len(db_snapshot.get('impacts', []))}", flush=True)
        print(f"bundle_rows={len(db_snapshot.get('bundles', []))}", flush=True)
        print(f"stix_audit_rows={len(db_snapshot.get('stix_audits', []))}", flush=True)
        print(f"bom_audit_rows={len(db_snapshot.get('bom_audits', []))}", flush=True)
        print(f"stix_queue_rows={len(db_snapshot.get('stix_queue', []))}", flush=True)
    else:
        print("No persisted attack snapshot was found.", flush=True)

    print(f"\nPassed {passed}/{len(checks)} checks", flush=True)

    critical_failures = {
        "raw_ingest_db",
        "phase3_bom_mentions",
        "phase3_initial_stix_payload",
        "dedup_attack_persisted",
        "taxonomy_persisted",
        "cvss_persisted",
        "ai_bom_persisted",
        "stix_persisted",
    }
    failed_critical = [check.name for check in checks if check.name in critical_failures and not check.ok]
    if failed_critical:
        print("Critical failures: " + ", ".join(failed_critical), flush=True)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a real WP1-1 mock-raw-intelligence parse-chain probe against the configured DB and LLM.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose structured outputs from Phase 3 and AI BOM state.",
    )
    args = parser.parse_args()
    return run_probe(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
