import json
import subprocess
import time
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sandbox_agent.api import create_router
from sandbox_agent.service import SandboxService, write_json


class Process:
    pid = 987654321

    def __init__(self):
        self.done = Event()
        self.code = 0

    def wait(self, timeout=None):
        if not self.done.wait(timeout):
            raise subprocess.TimeoutExpired("test", timeout)
        return self.code


@pytest.fixture
def setup(tmp_path, monkeypatch):
    processes, commands = [], []

    def popen(command, **kwargs):
        process = Process()
        processes.append(process)
        commands.append((command, kwargs))
        return process

    service = SandboxService(tmp_path / "runs", tmp_path / "runtime", popen)
    monkeypatch.setattr(
        service,
        "environment",
        lambda: {
            "DEEPSEEK_API_KEY": "test-secret-token",
            "DEEPSEEK_CHAT_MODEL": "test",
        },
    )
    service.python.parent.mkdir(parents=True)
    service.python.touch()
    app = FastAPI()
    app.include_router(create_router(service))
    app.include_router(create_router(service, legacy=True))
    with TestClient(app) as client:
        yield client, service, processes, commands
    for process in processes:
        process.done.set()
    finish(service)


def finish(service):
    deadline = time.monotonic() + 2
    while service.active and time.monotonic() < deadline:
        time.sleep(0.01)
    assert service.active is None


def request(tmp_path):
    return {
        "kind": "audit",
        "target_repo": str(tmp_path),
        "authorization_ref": "self-owned-fixture",
        "max_agent_calls": 5,
        "max_cost_usd": 1,
    }


def test_configuration_validation_and_missing_graph(setup, tmp_path):
    client, _service, processes, _commands = setup
    cap = client.get("/api/sandbox/overview").json()["capabilities"]
    assert cap["audit_ready"] and not cap["case_ready"]
    assert "test-secret-token" not in json.dumps(cap)
    assert client.post("/api/sandbox/runs", json={"kind": "audit"}).status_code == 422
    assert (
        client.post(
            "/api/sandbox/runs",
            json={**request(tmp_path), "target_repo": "https://example.com/repo"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/sandbox/runs", json={**request(tmp_path), "max_agent_calls": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/sandbox/runs",
            json={"kind": "case", "request": "offline prompt injection"},
        ).status_code
        == 503
    )
    assert not processes


def test_legacy_routes_share_jobs_queue_history_and_artifacts(setup, tmp_path):
    from red_team.service import RedTeamService

    client, service, processes, _commands = setup
    assert RedTeamService is SandboxService
    response = client.post("/api/redteam/runs", json=request(tmp_path))
    assert response.status_code == 202
    rid = response.json()["run_id"]
    assert client.get("/api/sandbox/overview").json()["active_run_id"] == rid
    assert client.post("/api/sandbox/runs", json=request(tmp_path)).status_code == 409
    assert len(processes) == 1
    assert client.get(f"/api/sandbox/runs/{rid}").json() == client.get(
        f"/api/redteam/runs/{rid}"
    ).json()
    result = service.folder(rid) / "results" / "assessment"
    result.mkdir(parents=True)
    (result / "report.md").write_text("# Existing report", encoding="utf-8")
    params = {"path": "results/assessment/report.md"}
    assert client.get(f"/api/sandbox/runs/{rid}/artifact", params=params).text == client.get(
        f"/api/redteam/runs/{rid}/artifact", params=params
    ).text == "# Existing report"
    assert client.get("/api/sandbox/runs?workspace=sandbox").json() == client.get(
        "/api/redteam/runs?workspace=redteam"
    ).json()
    schema = client.get("/openapi.json").json()["paths"]
    assert schema["/api/redteam/runs"]["post"]["deprecated"] is True
    assert not schema["/api/sandbox/runs"]["post"].get("deprecated", False)
    assert client.post("/api/pentest/runs", json={}).status_code == 404


def test_lifecycle_artifact_boundary_and_resume(setup, tmp_path):
    client, service, processes, commands = setup
    response = client.post("/api/sandbox/runs", json=request(tmp_path))
    assert response.status_code == 202
    rid = response.json()["run_id"]
    assert client.post("/api/sandbox/runs", json=request(tmp_path)).status_code == 409
    command, options = commands[0]
    assert isinstance(command, list) and not options.get("shell")
    assert options["start_new_session"] is True
    result = service.folder(rid) / "results" / "assessment"
    write_json(
        result / "run_state.json",
        {
            "phase": "interrupted",
            "agent_calls_used": 5,
            "cost_usd_used": 0.4,
            "findings": [],
        },
    )
    (result / "report.md").write_text("# Review\nVerified fixture.")
    (result / "run_metadata.json").write_text('{"authorization_ref":"private"}')
    (service.folder(rid) / "runtime.log").write_text("test-secret-token\n")
    processes[0].code = 3
    processes[0].done.set()
    finish(service)
    detail = client.get(f"/api/sandbox/runs/{rid}").json()
    assert detail["status"] == "interrupted" and detail["can_resume"]
    assert detail["state"]["agent_calls_used"] == 5
    assert "test-secret-token" not in "".join(detail["logs"])
    path = detail["artifacts"][0]["path"]
    download = client.get(f"/api/sandbox/runs/{rid}/artifact", params={"path": path})
    assert (
        download.status_code == 200
        and "attachment" in download.headers["content-disposition"]
    )
    for forbidden in [
        "../job.json",
        "job.json",
        "results/assessment/run_metadata.json",
    ]:
        assert (
            client.get(
                f"/api/sandbox/runs/{rid}/artifact", params={"path": forbidden}
            ).status_code
            == 404
        )
    (result / "attack.py").symlink_to(service.folder(rid) / "job.json")
    assert (
        client.get(
            f"/api/sandbox/runs/{rid}/artifact",
            params={"path": "results/assessment/attack.py"},
        ).status_code
        == 404
    )
    resumed = client.post(f"/api/sandbox/runs/{rid}/resume")
    assert resumed.status_code == 202
    assert resumed.json()["resume_caps"] == {"max_agent_calls": 10, "max_cost_usd": 1.4}
    assert "--resume" in commands[-1][0]
    processes[-1].done.set()
    finish(service)
    assert client.get(f"/api/sandbox/runs/{rid}").json()["status"] == "succeeded"
    assert client.post(f"/api/sandbox/runs/{rid}/resume").status_code == 409


def test_stop_and_restart_state(setup, tmp_path, monkeypatch):
    client, service, processes, _ = setup
    rid = client.post("/api/sandbox/runs", json=request(tmp_path)).json()["run_id"]
    monkeypatch.setattr(
        "sandbox_agent.service.os.killpg", lambda *args: processes[-1].done.set()
    )
    assert client.post(f"/api/sandbox/runs/{rid}/stop").status_code == 200
    finish(service)
    assert client.get(f"/api/sandbox/runs/{rid}").json()["status"] == "cancelled"
    job_path = service.folder(rid) / "job.json"
    payload = json.loads(job_path.read_text())
    write_json(job_path, {**payload, "status": "running"})
    assert client.get(f"/api/sandbox/runs/{rid}").json()["status"] == "interrupted"


def test_graph_promotes_only_validated_index_and_keeps_previous_on_failure(
    setup, tmp_path
):
    from types import SimpleNamespace

    from intel_agent.schemas import RawIntelItem

    client, service, processes, _commands = setup
    service.intel_store = SimpleNamespace(
        load_corpus_items=lambda: [
            RawIntelItem(
                item_id=str(i),
                title=f"Security {i}",
                summary="Prompt injection and defense controls",
                source_name="arxiv_api",
                source_uri=f"https://example.com/{i}",
            )
            for i in range(3)
        ]
    )
    response = client.post("/api/sandbox/graph/build", json={"limit": 2})
    assert response.status_code == 202
    rid = response.json()["run_id"]
    root = service.folder(rid) / "results" / "graph"
    assert len(json.loads((root / "input/intel_corpus.json").read_text())) == 2
    assert not service.graph_pointer.exists()
    assert client.post("/api/sandbox/graph/build", json={"limit": 2}).status_code == 409
    write_json(
        root / "manifest.json",
        {"status": "ready", "query_verified": True, "retrieval_mode": "global"},
    )
    processes[-1].done.set()
    finish(service)
    pointer = json.loads(service.graph_pointer.read_text())
    assert pointer["root"] == str(root.resolve())
    response = client.post("/api/sandbox/graph/build", json={"limit": 3})
    second = response.json()["run_id"]
    processes[-1].done.set()  # Missing validated manifest must never become active.
    finish(service)
    assert client.get(f"/api/sandbox/runs/{second}").json()["status"] == "failed"
    assert json.loads(service.graph_pointer.read_text()) == pointer


def test_workspaces_filter_history_before_limit_and_expose_active_kind(setup):
    client, service, _, _ = setup
    audit_id = f"rt_{0:032x}"
    for i in range(52):
        run_id = f"rt_{i:032x}"
        write_json(service.data_dir / run_id / "job.json", {
            "run_id": run_id,
            "kind": "audit" if i == 0 else "graph",
            "status": "succeeded",
            "created_at": f"2026-10-14T05:00:{i:02d}Z",
        })
    assert len(client.get("/api/sandbox/runs").json()) == 50
    graphs = client.get("/api/sandbox/runs?workspace=graph").json()
    audits = client.get("/api/sandbox/runs?workspace=sandbox").json()
    assert len(graphs) == 50 and all(row["kind"] == "graph" for row in graphs)
    assert [row["run_id"] for row in audits] == [audit_id]
    assert client.get("/api/sandbox/runs?workspace=other").status_code == 422
    service.active = graphs[0]["run_id"]
    try:
        overview = client.get("/api/sandbox/overview").json()
        assert overview["active_run_kind"] == "graph"
        assert overview["active_run_id"] == graphs[0]["run_id"]
    finally:
        service.active = None
