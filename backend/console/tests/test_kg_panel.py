"""Tests for KG panel persist + env config."""

from __future__ import annotations

import json
from pathlib import Path

from console.kg_panel import (
    _persist_record,
    _should_generate,
    default_kg_config,
    generate_bulk_from_db,
    list_kg_records,
)
from ctinexus_kg.schemas import (
    ItemKnowledgeGraphRecord,
    KgEligibilityDecision,
    KgGenerationConfig,
)
from intel_agent.persistence import JsonIntelRunStore
from intel_agent.tests.conftest import make_item


def test_kg_config_from_env_defaults(monkeypatch):
    monkeypatch.delenv("CTINEXUS_MODEL", raising=False)
    monkeypatch.delenv("GLM_MODEL", raising=False)
    monkeypatch.setenv("GLM_BASE_URL", "https://example.glm")
    cfg = KgGenerationConfig.from_env()
    assert cfg.model == "glm-4.7"
    assert cfg.embedding_model == "embedding-3"
    assert cfg.base_url == "https://example.glm"
    assert default_kg_config().model == "glm-4.7"


def test_persist_and_list_kg_records(tmp_path: Path, monkeypatch):
    store = JsonIntelRunStore(root_dir=tmp_path / "runs", kg_dir=tmp_path / "kgs")
    monkeypatch.setattr("console.kg_panel.default_store", lambda: store)
    monkeypatch.setattr("console.db_browser.default_store", lambda: store)
    monkeypatch.setattr("console.db_browser.EXPORT_DIR", tmp_path / "exports")

    graph_path = tmp_path / "item.json"
    graph_path.write_text(
        json.dumps({"IE": {"triplets": [{"s": "a", "r": "b", "o": "c"}]}}),
        encoding="utf-8",
    )
    item = make_item("nvd:kg-1", topics=["jailbreak"])
    record = ItemKnowledgeGraphRecord(
        run_id="run-kg",
        item_id=item.item_id,
        source_name=item.source_name,
        source_uri=item.source_uri,
        status="succeeded",
        eligibility=KgEligibilityDecision(
            item_id=item.item_id, eligible=True, matched_topics=["jailbreak"]
        ),
        triplet_count=1,
        entity_count=2,
        model="glm-4.7",
        embedding_model="embedding-3",
        ctinexus_json_path=str(graph_path),
    )
    _persist_record(record)
    loaded = store.load_knowledge_graph("nvd:kg-1")
    assert loaded is not None
    assert loaded["status"] == "succeeded"
    assert loaded["graph"]["IE"]["triplets"]

    msg, rows, csv_path = list_kg_records(limit=10)
    assert "1 KG" in msg
    assert rows[0][0] == "nvd:kg-1"
    assert csv_path and Path(csv_path).exists()


def test_bulk_generation_resumes_skips_success_and_isolates_item_failure(monkeypatch):
    docs = [
        make_item("nvd:done", topics=["jailbreak"]).model_dump(mode="json"),
        make_item("nvd:retry", topics=["jailbreak"]).model_dump(mode="json"),
        make_item("nvd:new", topics=["jailbreak"]).model_dump(mode="json"),
    ]

    class FakeStore:
        def query_items(self, **kwargs):
            assert kwargs["limit"] == 1000
            return docs

        def list_knowledge_graphs(self, **kwargs):
            return [
                {"item_id": "nvd:done", "status": "succeeded"},
                {"item_id": "nvd:retry", "status": "failed"},
            ]

    manifests = []

    class FakeGenerator:
        def __init__(self, config):
            self.config = config

        def generate_for_item(self, run_id, item, target_topics):
            assert target_topics
            if item.item_id == "nvd:retry":
                raise RuntimeError("transient provider error")
            return ItemKnowledgeGraphRecord(
                run_id=run_id,
                item_id=item.item_id,
                source_name=item.source_name,
                source_uri=item.source_uri,
                status="succeeded",
                eligibility=KgEligibilityDecision(
                    item_id=item.item_id,
                    eligible=True,
                    matched_topics=["jailbreak"],
                ),
                triplet_count=2,
                entity_count=3,
            )

        def write_manifest(self, run_id, records):
            manifests.append((run_id, [record.item_id for record in records]))

    persisted = []
    monkeypatch.setattr("console.kg_panel.default_store", lambda: FakeStore())
    monkeypatch.setattr("console.kg_panel.CtinexusKgGenerator", FakeGenerator)
    monkeypatch.setattr("console.kg_panel._persist_record", persisted.append)

    updates = list(generate_bulk_from_db(existing_policy="retry_failed"))
    summary = json.loads(updates[-1][0])

    assert summary["status"] == "completed"
    assert summary["scanned"] == 3
    assert summary["kg_ready"] == 3
    assert summary["selected"] == 2
    assert summary["skipped_existing"] == 1
    assert summary["processed"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert [record.item_id for record in persisted] == ["nvd:retry", "nvd:new"]
    assert "transient provider error" in persisted[0].error
    assert manifests == [("db-kg", ["nvd:retry", "nvd:new"])]
    assert len(updates[-1][1]) == 2


def test_bulk_existing_policy_semantics():
    assert _should_generate(None, "missing_only") is True
    assert _should_generate("failed", "missing_only") is False
    assert _should_generate("failed", "retry_failed") is True
    assert _should_generate("succeeded", "retry_failed") is False
    assert _should_generate("succeeded", "regenerate_all") is True
