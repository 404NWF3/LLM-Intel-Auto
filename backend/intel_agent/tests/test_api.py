"""HTTP contract tests with real persistence and an offline controller."""
from threading import Event
import time

import mongomock
import pytest
from fastapi.testclient import TestClient

from intel_agent.api import CollectionService, create_app
from intel_agent.engine.controller import IntelAgentController
from intel_agent.memory.playbook import PlaybookStore
from intel_agent.mongo_store import MongoIntelRunStore
from intel_agent.persistence import JsonIntelRunStore
from intel_agent.schemas import IntelRunBlackboard
from .conftest import make_item
from .test_controller import _fake_loop, _stop_engine


def wait_done(service):
    deadline = time.monotonic() + 5
    while service.active is not None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert service.active is None


@pytest.mark.parametrize("backend", ["json", "mongo"])
def test_real_controller_http_lifecycle(tmp_path, backend):
    store = (JsonIntelRunStore(tmp_path / "runs") if backend == "json" else
             MongoIntelRunStore(database=mongomock.MongoClient().db))
    def factory(store):
        return IntelAgentController(store=store, playbook=PlaybookStore(path=None),
                                    loop=_fake_loop(), decision_engine=_stop_engine())
    service = CollectionService(store, factory, tmp_path)
    with TestClient(create_app(service)) as client:
        assert client.get("/api/intel/overview").json()["item_count"] == 0
        response = client.post("/api/intel/runs", json={"mode": "full", "max_rounds": 1, "max_api_calls": 2})
        assert response.status_code == 202
        rid = response.json()["run_id"]
        wait_done(service)
        overview = client.get("/api/intel/overview").json()
        assert overview["item_count"] == 2
        assert overview["coverage"]["prompt injection"] == 2
        detail = client.get(f"/api/intel/runs/{rid}").json()
        assert detail["status"] == "succeeded"
        assert detail["events"]
        assert detail["metrics"]["api_calls_used"] == 1
        assert client.get("/api/intel/runs").json()[0]["run_id"] == rid
        assert len(client.get("/api/intel/items", params={"run_id": rid, "topic": "prompt injection"}).json()) == 2
        assert client.get("/api/intel/items", params={"text": "does not exist"}).json() == []
        # Literal regex metacharacters must not match every Mongo document.
        assert client.get("/api/intel/items", params={"text": ".*"}).json() == []
        assert client.get("/api/intel/runs/missing").status_code == 404


def test_validation_concurrency_failure_and_restart(tmp_path):
    started, release = Event(), Event()
    received_budgets = []
    class FailingController:
        def __init__(self, **kwargs): pass
        def run(self, **kwargs):
            received_budgets.append(kwargs["budget"])
            started.set()
            assert release.wait(3)
            raise RuntimeError("test failure")
    service = CollectionService(JsonIntelRunStore(tmp_path / "runs"), FailingController, tmp_path)
    with TestClient(create_app(service)) as client:
        for body in [{"mode": "invalid"}, {"max_rounds": 0}, {"max_api_calls": 0}, {"max_rounds": 1.5}, {"max_api_calls": 1.5}, {"window_days": 0}]:
            assert client.post("/api/intel/runs", json=body).status_code == 422
        response = client.post("/api/intel/runs", json={"focus": "prompt injection", "max_rounds": 200, "max_api_calls": 10000})
        assert response.status_code == 202
        rid = response.json()["run_id"]
        assert started.wait(1)
        assert received_budgets[0].max_rounds == 200
        assert received_budgets[0].max_api_calls == 10000
        try:
            assert client.post("/api/intel/runs", json={}).status_code == 409
            assert client.get("/api/intel/overview").json()["active"]["run_id"] == rid
            assert client.get(f"/api/intel/runs/{rid}").json()["status"] == "running"
        finally:
            release.set()
        wait_done(service)
        assert client.get(f"/api/intel/runs/{rid}").json()["status"] == "failed"
        assert client.get("/api/intel/runs").json()[0]["error"]
    restarted = CollectionService(service.store, data_dir=tmp_path)
    restarted._save({"run_id": "stale", "status": "running", "saved_at": "2026-10-14"})
    with TestClient(create_app(restarted)) as client:
        assert client.get("/api/intel/runs/stale").json()["status"] == "interrupted"
        assert client.get("/api/intel/runs").json()[0]["status"] in {"failed", "interrupted"}


def test_partial_trace_and_item_filter(tmp_path):
    store = JsonIntelRunStore(tmp_path / "runs")
    store.save_run(IntelRunBlackboard(run_id="saved", run_goal="test", raw_items=[make_item("one")]))
    (tmp_path / "traces").mkdir()
    (tmp_path / "traces/saved.jsonl").write_text('{"event":"test","ts":"2026-10-14"}\n{"event":')
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path))) as client:
        assert len(client.get("/api/intel/runs/saved").json()["events"]) == 1
        assert len(client.get("/api/intel/items", params={"source": "nvd_cve_api"}).json()) == 1
        assert client.get("/api/intel/items", params={"source": "arxiv_api"}).json() == []
        assert client.get("/api/intel/items?limit=10000").status_code == 422


@pytest.mark.parametrize("backend", ["json", "mongo"])
def test_export_all_full_items_across_runs(tmp_path, backend):
    store = (JsonIntelRunStore(tmp_path / "runs") if backend == "json" else
             MongoIntelRunStore(database=mongomock.MongoClient().db))
    full_text = '完整原文\n代码转义：\\n；逗号，双引号"\n' * 3000 + "FINAL RAW MARKER"
    full_summary = "论文完整 summary\n" * 300 + "FINAL SUMMARY MARKER"
    paper = make_item("arxiv:full", source_name="arxiv_api", raw_text=full_text,
                      summary=full_summary)
    paper.metadata["nested"] = {"references": ["https://example/paper"], "unicode": "中文"}
    store.save_run(IntelRunBlackboard(
        run_id="first", run_goal="test", raw_items=[paper, *[make_item(str(i)) for i in range(205)]],
    ))
    store.save_run(IntelRunBlackboard(run_id="second", run_goal="test", raw_items=[paper]))

    with TestClient(create_app(CollectionService(store, data_dir=tmp_path))) as client:
        assert len(client.get("/api/intel/items").json()) == 100
        # Export ignores list limits and filters, including the selected run.
        response = client.get("/api/intel/export?limit=1&source=missing&topic=missing&text=missing&run_id=second")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.headers["content-disposition"].startswith('attachment; filename="intel-agent-items-')
        assert response.headers["content-disposition"].endswith('.json"')
        assert response.headers["cache-control"] == "no-store"
        exported = response.json()
        assert exported["format"] == "intel-agent.items.v1"
        assert exported["exported_at"]
        assert exported["item_count"] == len(exported["items"]) == 206
        assert len({item["item_id"] for item in exported["items"]}) == 206
        row = next(item for item in exported["items"] if item["item_id"] == paper.item_id)
        assert row == client.get("/api/intel/items/arxiv:full").json()
        assert row["raw_text"] == full_text
        assert row["summary"] == full_summary
        assert row["metadata"] == paper.metadata
        assert set(row["run_ids"]) == {"first", "second"}


@pytest.mark.parametrize("backend", ["json", "mongo"])
def test_empty_export(tmp_path, backend):
    store = (JsonIntelRunStore(tmp_path / "runs") if backend == "json" else
             MongoIntelRunStore(database=mongomock.MongoClient().db))
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path))) as client:
        response = client.get("/api/intel/export")
        assert response.status_code == 200
        assert response.json()["item_count"] == 0
        assert response.json()["items"] == []


def test_export_storage_failure_is_not_downloaded(tmp_path, monkeypatch):
    store = JsonIntelRunStore(tmp_path / "runs")
    def fail(**kwargs):
        raise OSError("test storage failure")
    monkeypatch.setattr(store, "query_items", fail)
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path)),
                    raise_server_exceptions=False) as client:
        response = client.get("/api/intel/export")
        assert response.status_code == 503
        assert response.json()["detail"]
        assert "content-disposition" not in response.headers


@pytest.mark.parametrize("backend", ["json", "mongo"])
def test_home_stats_use_full_deduplicated_corpus(tmp_path, backend):
    from common.topics import CORE_SECURITY_TOPICS
    from pentest_agent.service import PentestService
    store = (JsonIntelRunStore(tmp_path / "runs") if backend == "json" else
             MongoIntelRunStore(database=mongomock.MongoClient().db))
    pentest = PentestService(store, data_dir=tmp_path / "pentest")
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path), pentest_service=pentest)) as client:
        empty = client.get("/api/stats")
        assert empty.status_code == 200
        assert empty.headers["cache-control"] == "no-store"
        assert empty.json()["item_count"] == empty.json()["core_coverage_pct"] == 0
        assert empty.json()["script_count"] == 0
        older = make_item("older", source_name="arxiv_api")
        older.metadata["topics"] = ["jailbreak", "system prompt leakage"]
        store.save_run(IntelRunBlackboard(run_id="first", run_goal="test", raw_items=[
            older, *[make_item(str(i)) for i in range(205)],
        ]))
        store.save_run(IntelRunBlackboard(run_id="second", run_goal="test", raw_items=[make_item("0")]))
        stats = client.get("/api/stats").json()
        assert stats["item_count"] == 206
        assert stats["source_count"] == 2
        assert stats["core_topics_covered"] == 2
        assert stats["core_topics_total"] == len(CORE_SECURITY_TOPICS)
        assert stats["core_coverage_pct"] == round(200 / len(CORE_SECURITY_TOPICS), 1)
        assert stats["updated_at"]


def test_home_stats_storage_failure_is_not_zero(tmp_path, monkeypatch):
    store = JsonIntelRunStore(tmp_path / "runs")
    def fail(**kwargs):
        raise OSError("test storage failure")
    monkeypatch.setattr(store, "query_items", fail)
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path)),
                    raise_server_exceptions=False) as client:
        response = client.get("/api/stats")
        assert response.status_code == 503
        assert "item_count" not in response.json()
