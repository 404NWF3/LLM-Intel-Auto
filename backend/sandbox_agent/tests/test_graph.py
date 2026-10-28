from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sandbox_agent.graph import GraphBuildRequest, export_corpus


def item(identifier, summary, score=0.5):
    return SimpleNamespace(
        item_id=identifier,
        title=identifier,
        summary=summary,
        relevance_score=score,
        source_name="arxiv_api",
        source_uri=f"https://example.com/{identifier}",
        metadata={},
        published_at=None,
        fetched_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )


def test_corpus_is_deduplicated_filtered_and_traceable():
    store = SimpleNamespace(
        load_corpus_items=lambda: [
            item("a", "obsolete"),
            item("a", "prompt injection updated", 0.9),
            item("b", "Prompt Injection control", 0.8),
            item("c", "irrelevant"),
            item("d", ""),
        ]
    )
    config = GraphBuildRequest(limit=2, focus="prompt injection")
    documents, source = export_corpus(store, config)
    assert source["available_items"] == 4
    assert source["matching_items"] == source["indexed_items"] == 2
    assert [row["item_id"] for row in source["sources"]] == ["a", "b"]
    assert source["sources"][0]["document_id"] == documents[0]["id"]
    assert "https://example.com/a" in documents[0]["text"]
    assert "updated" in documents[0]["text"] and "obsolete" not in documents[0]["text"]
    assert export_corpus(store, config)[1]["corpus_sha256"] == source["corpus_sha256"]


def test_empty_scope_does_not_launch_model_work():
    with pytest.raises(HTTPException) as exc:
        export_corpus(
            SimpleNamespace(load_corpus_items=lambda: [item("a", "")]),
            GraphBuildRequest(),
        )
    assert exc.value.status_code == 422
