"""Local HTTP lifecycle with actual sklearn worker and isolated output files."""
import csv
import io
import sys
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intel_agent.researcher.api import create_router
from intel_agent.researcher.data import demo_csv, load_dataset
from intel_agent.researcher.service import ResearcherService, write_json


@pytest.fixture
def research_client(tmp_path):
    service = ResearcherService(tmp_path)
    app = FastAPI()
    app.include_router(create_router(service))
    with TestClient(app) as client:
        yield client, service
    service.shutdown()


def wait_done(service, timeout=30):
    deadline = time.monotonic() + timeout
    while service.active and time.monotonic() < deadline:
        time.sleep(0.03)
    assert service.active is None


def test_demo_real_worker_history_and_download(research_client):
    client, service = research_client
    dataset = client.post("/api/researcher/datasets/demo").json()
    assert dataset["suggested_label"] == "label"
    response = client.post("/api/researcher/runs", json={
        "dataset_id": dataset["dataset_id"], "label_column": "label", "max_rounds": 3, "use_llm": False,
    })
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    wait_done(service)
    job = client.get(f"/api/researcher/runs/{run_id}").json()
    assert job["status"] == "succeeded", job
    assert len(job["rounds"]) == 3
    assert job["metric"] == "validation_ap"
    assert 0 <= job["final_metrics"]["ap"] <= 1
    assert job["artifacts_ready"] is True
    assert job["events"]
    assert client.get("/api/researcher/runs").json()[0]["run_id"] == run_id
    assert client.get(f"/api/researcher/runs/{run_id}/model").status_code == 200
    scores = client.get(f"/api/researcher/runs/{run_id}/scores")
    assert scores.status_code == 200 and "text/csv" in scores.headers["content-type"]
    assert client.get("/api/researcher/overview").json()["active"] is None
    assert client.post(f"/api/researcher/runs/{run_id}/stop").json()["status"] == "succeeded"


def test_upload_validation_and_withheld_label(research_client):
    client, service = research_client
    assert client.post("/api/researcher/datasets", content=b"x\n1\n").status_code == 422
    assert client.post("/api/researcher/datasets", content=b"x,x\n1,2\n").status_code == 422
    assert client.post("/api/researcher/datasets", content=b"x" * (8 * 1024 * 1024 + 1)).status_code == 413
    response = client.post("/api/researcher/datasets?filename=../sample.csv", content=demo_csv())
    assert response.status_code == 201
    dataset = response.json()
    assert dataset["name"] == "sample.csv"
    path, _ = service.dataset(dataset["dataset_id"])
    X, y, features, ignored = load_dataset(path, None)
    assert X.shape == (300, 6) and y is None
    assert "label" not in features and "label" in ignored
    for config in [{"max_rounds": 0}, {"max_rounds": 21}, {"label_column": "missing"}]:
        assert client.post("/api/researcher/runs", json={"dataset_id": dataset["dataset_id"], **config}).status_code == 422
    assert client.get("/api/researcher/runs/not-a-run").status_code == 404
    assert client.post("/api/researcher/runs", json={"dataset_id": "../../secret"}).status_code == 422


def test_input_numeric_and_label_boundaries(tmp_path):
    path = tmp_path / "input.csv"
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["value", "note", "empty", "label"])
    for i in range(30):
        writer.writerow([i if i % 3 else "", "text", "", int(i >= 24)])
    path.write_text(stream.getvalue())
    X, y, features, ignored = load_dataset(path, "label")
    assert X.shape == (30, 1) and y.sum() == 6
    assert features == ["value"] and ignored == ["note", "empty"]
    path.write_text(stream.getvalue().replace("text", "inf"))
    with pytest.raises(ValueError, match="无穷"):
        load_dataset(path, "label")


def test_concurrency_cancellation_and_interruption(research_client, monkeypatch):
    import intel_agent.researcher.service as module
    client, service = research_client
    real_popen = module.subprocess.Popen

    def slow_worker(args, **kwargs):
        return real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

    monkeypatch.setattr(module.subprocess, "Popen", slow_worker)
    dataset = client.post("/api/researcher/datasets/demo").json()
    config = {"dataset_id": dataset["dataset_id"], "use_llm": False}
    response = client.post("/api/researcher/runs", json=config)
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert client.post("/api/researcher/runs", json=config).status_code == 409
    assert client.get(f"/api/researcher/runs/{run_id}/model").status_code == 404
    assert client.post(f"/api/researcher/runs/{run_id}/stop").status_code == 200
    wait_done(service, timeout=6)
    assert client.get(f"/api/researcher/runs/{run_id}").json()["status"] == "cancelled"
    job = service.job(run_id)
    job["status"] = "running"
    write_json(service.folder(run_id) / "job.json", job)
    restarted = ResearcherService(service.data_dir)
    assert restarted.job(run_id)["status"] == "interrupted"
