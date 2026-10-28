from __future__ import annotations

import csv
import json
from pathlib import Path

import mongomock
import pytest
from fastapi.testclient import TestClient

from intel_agent.api import CollectionService, create_app
from intel_agent.content import preserve_text
from intel_agent.maintenance import backfill_raw_text, import_csv, read_items_csv
from intel_agent.mongo_store import MongoIntelRunStore
from intel_agent.persistence import JsonIntelRunStore
from intel_agent.schemas import IntelRunBlackboard, RawIntelItemBatch
from intel_agent.tests.conftest import make_item


@pytest.fixture(params=["json", "mongo"])
def store(request, tmp_path):
    if request.param == "json":
        return JsonIntelRunStore(tmp_path / "runs")
    return MongoIntelRunStore(database=mongomock.MongoClient()["repair_test"])


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_csv_import_lossless_idempotent_and_preserves_provenance(store, tmp_path):
    raw = '多行摘要, "quoted"\n' * 2000 + "END"
    path = tmp_path / "history.csv"
    write_csv(path, [{"_id": "arxiv:1234.56789v1", "source_name": "arxiv_api",
                     "source_uri": "https://arxiv.org/abs/1234.56789v1", "raw_text": raw,
                     "summary": raw, "title": "paper", "metadata.topics[0]": "jailbreak",
                     "metadata.authors[0]": "Jane", "metadata.authors[1]": "Joe",
                     "metadata.source_query_params.arxiv_start": "20",
                     "metadata.relevance.score": "0.8", "run_ids[0]": "historic",
                     "first_run_id": "historic", "first_seen_at": "2025-01-01T00:00:00Z"}])
    report = import_csv(store, path, output_dir=tmp_path / "import-one")
    assert report["new_items"] == 1
    item = store.get_item("arxiv:1234.56789v1")
    assert item["raw_text"] == raw
    assert item["summary"] == raw
    assert item["metadata"]["authors"] == ["Jane", "Joe"]
    assert item["metadata"]["source_query_params"]["arxiv_start"] == 20
    assert item["first_run_id"] == "historic"
    assert store.query_items(run_id="historic")[0]["raw_text"] == raw
    second = import_csv(store, path, output_dir=tmp_path / "import-two")
    assert second["new_items"] == 0
    assert store.distinct_item_count() == 1
    assert store.run_count() == 1
    assert store.get_item(item["item_id"])["raw_text"] == raw
    store.update_item_texts({item["item_id"]: {"raw_text": "Verified revised source text."}})
    import_csv(store, path, output_dir=tmp_path / "import-three")
    assert store.get_item(item["item_id"])["raw_text"] == "Verified revised source text."


def test_malformed_csv_does_not_partially_import(store, tmp_path):
    path = tmp_path / "invalid.csv"
    write_csv(path, [{"item_id": "one", "source_name": "arxiv_api", "source_uri": "https://arxiv.org"},
                     {"item_id": "", "source_name": "arxiv_api", "source_uri": "https://arxiv.org"}])
    with pytest.raises(ValueError, match="row 3"):
        import_csv(store, path, output_dir=tmp_path / "invalid")
    assert store.run_count() == 0
    assert not (tmp_path / "invalid").exists()


def test_repeated_collection_and_api_never_clip_raw_text(store, tmp_path):
    raw = "first paragraph\n" + "原始内容" * 4000 + "FINAL MARKER"
    item = make_item("arxiv:hep-th/1234567v1", source_name="arxiv_api", raw_text=raw, summary=raw)
    store.save_run(IntelRunBlackboard(run_id="one", run_goal="test", raw_items=[item]))
    item.raw_text = raw[:50] + "..."
    item.summary = raw[:50] + "..."
    store.save_run(IntelRunBlackboard(run_id="two", run_goal="test", raw_items=[item]))
    assert store.get_item(item.item_id)["raw_text"] == raw
    assert store.load_corpus_items()[0].raw_text == raw
    assert store.load_run_payload("two")["blackboard"]["raw_items"][0]["raw_text"] == raw
    with TestClient(create_app(CollectionService(store, data_dir=tmp_path / "jobs"))) as client:
        assert client.get("/api/intel/items/arxiv:hep-th/1234567v1").json()["raw_text"] == raw
        assert "raw_text" not in client.get("/api/intel/items").json()[0]
        assert client.get("/api/intel/items/absent").status_code == 404


def test_preserve_text_accepts_real_revisions():
    assert preserve_text("Updated description.", "An old and much longer description.") == "Updated description."
    assert preserve_text(None, "full text") == "full text"
    assert preserve_text("start...", "start continues") == "start continues"
    assert preserve_text("source\n", "source\\n") == "source\n"
    assert preserve_text("source\\n", "source\n") == "source\n"


def test_backfill_updates_existing_runs_without_inventing_source_content(store, tmp_path):
    item = make_item("arxiv:one", source_name="arxiv_api", raw_text="", summary="full\nsummary")
    uncertain = make_item("arxiv:two", source_name="arxiv_api", raw_text="source...", summary="source...")
    failed = make_item("osv:missing", source_name="osv_dev_api", raw_text="", summary="short heading")
    board = IntelRunBlackboard(run_id="completed", run_goal="test", raw_items=[item, uncertain, failed])
    store.save_run(board, [RawIntelItemBatch(items=board.raw_items)])
    original = store.load_latest_payload()

    def fetcher(row):
        if row.item_id == "osv:missing":
            raise TimeoutError("offline")
        assert row.item_id == "arxiv:two"
        return "source...", "https://arxiv.org/abs/two"

    report = backfill_raw_text(store, output_dir=tmp_path / "repair", fetcher=fetcher)
    assert report["text_updates"] == 1
    assert store.get_item(item.item_id)["raw_text"] == "full\nsummary"
    assert store.get_item(uncertain.item_id)["raw_text"] == "source..."
    assert report["missing_after"] == 1
    assert {r["status"] for r in report["results"]} == {
        "recovered_from_summary", "source_ends_with_ellipsis", "fetch_failed"}
    latest = store.load_latest_payload()
    assert latest["saved_at"] == original["saved_at"]
    assert latest["run_id"] == "completed"
    assert store.run_count() == 1
    assert (tmp_path / "repair/backup").exists()
    if isinstance(store, JsonIntelRunStore):
        assert latest["raw_item_batches"][0]["items"][0]["raw_text"] == "full\nsummary"
        backup = json.loads((tmp_path / "repair/backup/intel_runs/completed.json").read_text())
        assert backup["blackboard"]["raw_items"][0]["raw_text"] == ""


def test_csv_export_roundtrip_keeps_full_text(store, tmp_path, monkeypatch):
    from console.db_browser import query_items_panel
    item = make_item("nvd:long", summary="完整摘要" * 500, raw_text="完整原文\n" * 3000)
    store.save_run(IntelRunBlackboard(run_id="one", run_goal="test", raw_items=[item]))
    monkeypatch.setattr("console.db_browser.default_store", lambda: store)
    monkeypatch.setattr("console.db_browser.EXPORT_DIR", tmp_path / "exports")
    _, _, path = query_items_panel("", "", "", "", 100)
    exported, _ = read_items_csv(Path(path))
    assert exported[0].raw_text == item.raw_text
    assert exported[0].summary == item.summary


def test_compass_escaped_newlines_use_source_without_corrupting_code(store, tmp_path):
    source = '### Details\nprint("\\n")\nend'
    exported = source.replace('\n', '\\n')
    item = make_item('osv:example', source_name='osv_dev_api', raw_text=exported)
    store.save_run(IntelRunBlackboard(run_id='escaped', run_goal='test', raw_items=[item]))
    report = backfill_raw_text(store, output_dir=tmp_path / 'escapes',
                               fetcher=lambda _: (source, 'https://api.osv.dev/v1/vulns/example'))
    assert store.get_item(item.item_id)['raw_text'] == source
    assert 'print("\\n")' in store.get_item(item.item_id)['raw_text']
    assert report['results'][0]['status'] == 'source_newlines_restored'
    assert preserve_text(exported, source) == source


def test_backfill_repairs_older_occurrences_from_existing_history(tmp_path):
    store = JsonIntelRunStore(tmp_path / 'runs')
    item = make_item('osv:shared', source_name='osv_dev_api', raw_text='')
    store.save_run(IntelRunBlackboard(run_id='old', run_goal='test', raw_items=[item]))
    item.raw_text = 'complete original\nwith paragraphs'
    store.save_run(IntelRunBlackboard(run_id='new', run_goal='test', raw_items=[item]))
    report = backfill_raw_text(store, output_dir=tmp_path / 'history-repair',
                               fetcher=lambda _: pytest.fail('No network needed'))
    assert store.load_run_payload('old')['blackboard']['raw_items'][0]['raw_text'] == item.raw_text
    assert report['results'][0]['status'] == 'recovered_from_history'
    assert report['text_updates'] == 1
