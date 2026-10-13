from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routers import wp12
from backend.api.wp12_run_store import Wp12RunStore
from backend.agents.saads_wp12.data.models import Wp12AttackFeedItem


def _build_item(
    attack_id: str,
    attack_code: str,
    canonical_name: str,
    summary: str,
    *,
    attack_family: str = "prompt_injection",
    score: float = 7.5,
) -> Wp12AttackFeedItem:
    return Wp12AttackFeedItem(
        attack_id=attack_id,
        attack_code=attack_code,
        canonical_name=canonical_name,
        attack_family=attack_family,
        severity_level="high",
        entry_status="active",
        summary=summary,
        last_seen_at="2026-04-11T00:00:00+00:00",
        primary_cvss_version="3.1",
        primary_cvss_base_score=score,
        primary_cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L",
        primary_cvss_severity_label="high",
        taxonomy_type="OWASP_LLM",
        taxonomy_code="LLM01",
        taxonomy_name="Prompt Injection",
        component_id="cmp-001",
        component_name="langchain",
        version_constraint_raw="*",
        normalized_constraint="*",
        component_impact_scope="retrieval_pipeline",
        asset_id="asset-001",
        asset_type="payload_template",
        asset_name="seed-asset",
        artifact_uri="mock://asset.json",
        qa_status="reviewed",
        active=True,
    )


class StubProvider:
    def __init__(self, items: list[Wp12AttackFeedItem]):
        self.items = items

    def list_attack_feed_snapshots(self) -> list[Wp12AttackFeedItem]:
        return list(self.items)

    def get_attack_feed_item(self, attack_id: str | None = None) -> Wp12AttackFeedItem:
        if attack_id is None:
            return self.items[0]
        for item in self.items:
            if item.attack_id == attack_id:
                return item
        raise KeyError(attack_id)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.state.wp12_run_store = Wp12RunStore()
    app.include_router(wp12.router)
    return app


def _build_stage_handlers(
    tmp_path: Path,
    *,
    verdict: str = "planned",
    valid: bool = True,
    package_kind: str = "standard",
    generation_mode: str = "standard",
    first_stage_sleep: float = 0.0,
) -> list[tuple[str, object]]:
    run_root = tmp_path / "artifacts"
    run_root.mkdir(parents=True, exist_ok=True)

    def ingest(state: dict) -> dict:
        if first_stage_sleep:
            time.sleep(first_stage_sleep)
        return {
            "run_id": state["run_id"],
            "attack_id": state["attack_id"],
            "intel_raw": {"attack_id": state["attack_id"]},
            "audit_log": [{"event": "ingested"}],
        }

    def normalize(state: dict) -> dict:
        return {
            "intel_normalized": {
                "attack_id": state["attack_id"],
                "attack_code": "WP12-PI-001",
                "canonical_name": "Prompt Injection",
            },
            "attack_family": "prompt_injection",
            "risk_flags": [],
        }

    def understand(state: dict) -> dict:
        return {
            "threat_understanding": {
                "threat_summary": "summary",
                "attack_mechanism": "mechanism",
                "target_surface": "retrieval_context",
                "taxonomy": {"code": "LLM01"},
            },
            "execution_assessment": {
                "execution_eligibility": "ready",
                "test_readiness": "ready",
                "execution_mode": "standard",
                "execution_blockers": [],
            },
            "scope_assessment": {"in_scope": True, "supported_family": "prompt_injection"},
            "evidence_and_context": {},
            "uncertainty_report": {"known_gaps": [], "missing_knowledge": []},
            "threat_profile": {"confidence": 0.92, "candidate_families": []},
            "target_surface": "retrieval_context",
            "confidence": 0.92,
            "candidate_families": [],
            "classification_rationale": {},
            "missing_knowledge": [],
            "test_readiness": "ready",
            "execution_eligibility": "ready",
            "can_build_env": True,
            "should_execute": True,
            "execution_mode": "standard",
        }

    def generate_package(state: dict) -> dict:
        return {
            "test_package": {
                "package_id": "pkg-001",
                "package_kind": package_kind,
                "attack_family": "prompt_injection",
                "target_surface": "retrieval_context",
                "objective": "objective",
                "attack_hypothesis": "hypothesis",
                "payload_plan": [],
                "execution_plan": {},
                "success_criteria": [],
                "failure_signals": [],
                "evidence_hooks": [],
                "assumptions": [],
                "environment_assumptions": [],
                "known_gaps": [],
                "recommended_follow_up": [],
                "evidence_collection_plan": {},
                "script_blueprint": {},
                "target_artifacts": [],
                "family_specific_strategy": {},
                "metadata": {},
                "generation_mode": generation_mode,
            },
            "package_version": 2,
        }

    def validate(state: dict) -> dict:
        return {
            "package_validation": {
                "valid": valid,
                "missing_fields": [],
                "validation_errors": [] if valid else ["invalid package"],
            }
        }

    def finalize(state: dict) -> dict:
        return {"verdict": verdict, "env_status": "not_applicable_plan_generation"}

    def persist(state: dict) -> dict:
        run_dir = run_root / state["run_id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        plan_path = run_dir / f"{state['attack_id']}_plan.md"
        presentation_path = run_dir / f"{state['attack_id']}_presentation.json"
        raw_state_path = run_dir / f"{state['attack_id']}_raw.json"

        presentation_payload = {
            "run_id": state["run_id"],
            "attack_id": state["attack_id"],
            "threat_understanding": state["threat_understanding"],
            "execution_assessment": state["execution_assessment"],
            "package_validation": state["package_validation"],
            "test_package": state["test_package"],
        }
        plan_path.write_text("# Test Plan\n\nGenerated plan body.", encoding="utf-8")
        presentation_path.write_text(
            json.dumps(presentation_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raw_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "persistence_path": str(run_dir),
            "plan_path": str(plan_path),
            "presentation_state_path": str(presentation_path),
            "raw_state_path": str(raw_state_path),
        }

    return [
        ("ingest_intel", ingest),
        ("normalize_intel", normalize),
        ("understand_threat_subgraph", understand),
        ("generate_test_package_subgraph", generate_package),
        ("validate_test_package", validate),
        ("finalize_plan_result", finalize),
        ("persist_plan_artifacts", persist),
    ]


def _wait_for_terminal(client: TestClient, run_id: str, *, timeout_s: float = 3.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(f"/api/wp12/runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not reach a terminal state")


@pytest.fixture(autouse=True)
def _reset_run_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wp12, "_RUN_LOCK", asyncio.Lock())


def test_feed_search_filters_and_orders(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = StubProvider(
        [
            _build_item("atk-001", "WP12-PI-001", "Prompt Injection", "matches tool", score=7.0),
            _build_item("atk-002", "WP12-TOOL-001", "Tool Hijack", "matches tool strongly", attack_family="tool_hijack", score=9.1),
            _build_item("atk-003", "WP12-DLG-001", "Dialogue Drift", "dialogue only", attack_family="long_horizon_dialogue", score=8.0),
        ]
    )
    monkeypatch.setattr(wp12, "get_attack_feed_provider", lambda: provider)

    with TestClient(_build_app()) as client:
        response = client.get("/api/wp12/feed?q=tool&limit=10")

        assert response.status_code == 200
        payload = response.json()
        assert [item["attack_id"] for item in payload] == ["atk-002", "atk-001"]

        detail = client.get("/api/wp12/feed/atk-002")
        assert detail.status_code == 200
        assert detail.json()["attack_code"] == "WP12-TOOL-001"


def test_run_lifecycle_and_latest_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider = StubProvider([_build_item("atk-001", "WP12-PI-001", "Prompt Injection", "summary")])
    monkeypatch.setattr(wp12, "get_attack_feed_provider", lambda: provider)
    monkeypatch.setattr(wp12, "_STAGE_HANDLERS", _build_stage_handlers(tmp_path))

    with TestClient(_build_app()) as client:
        start = client.post("/api/wp12/runs", json={"attack_id": "atk-001"})

        assert start.status_code == 201
        run_id = start.json()["run_id"]

        final_status = _wait_for_terminal(client, run_id)
        assert final_status["status"] == "succeeded"

        result = client.get(f"/api/wp12/runs/{run_id}/result")
        assert result.status_code == 200
        payload = result.json()
        assert payload["verdict"] == "planned"
        assert payload["plan_markdown"].startswith("# Test Plan")
        assert payload["artifacts"]["plan_path"].endswith("_plan.md")

        latest = client.get("/api/wp12/runs/latest/result")
        assert latest.status_code == 200
        assert latest.json()["run_id"] == run_id


def test_parallel_start_conflict_and_cancel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider = StubProvider([_build_item("atk-001", "WP12-PI-001", "Prompt Injection", "summary")])
    monkeypatch.setattr(wp12, "get_attack_feed_provider", lambda: provider)
    monkeypatch.setattr(
        wp12,
        "_STAGE_HANDLERS",
        _build_stage_handlers(tmp_path, first_stage_sleep=0.35),
    )

    with TestClient(_build_app()) as client:
        first = client.post("/api/wp12/runs", json={"attack_id": "atk-001"})
        assert first.status_code == 201
        run_id = first.json()["run_id"]

        conflict = client.post("/api/wp12/runs", json={"attack_id": "atk-001"})
        assert conflict.status_code == 409

        cancel = client.delete(f"/api/wp12/runs/{run_id}")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelling"

        final_status = _wait_for_terminal(client, run_id)
        assert final_status["status"] == "cancelled"

        latest = client.get("/api/wp12/runs/latest/result")
        assert latest.status_code == 404


def test_run_history_contains_sse_compatible_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = StubProvider([_build_item("atk-001", "WP12-PI-001", "Prompt Injection", "summary")])
    monkeypatch.setattr(wp12, "get_attack_feed_provider", lambda: provider)
    monkeypatch.setattr(wp12, "_STAGE_HANDLERS", _build_stage_handlers(tmp_path))

    app = _build_app()
    with TestClient(app) as client:
        start = client.post("/api/wp12/runs", json={"attack_id": "atk-001"})
        run_id = start.json()["run_id"]
        _wait_for_terminal(client, run_id)

        record = app.state.wp12_run_store.get(run_id)
        assert record is not None

        event_types = [payload.get("type") for payload in record.log_history]
        assert event_types[0] == "init"
        assert event_types.count("node_complete") == len(wp12._STAGE_HANDLERS)
        assert event_types[-1] == "done"
