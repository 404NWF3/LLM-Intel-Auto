from __future__ import annotations

from datetime import datetime, timezone

from console.intel_dashboard import build_dashboard_data, refresh_intel_dashboard
from intel_agent.schemas import (
    CandidateTopic,
    IntelRunBlackboard,
    QueryCallOutcome,
    RawIntelItem,
)

NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _item(
    item_id: str,
    source: str,
    *,
    title: str,
    relevance: float = 0.9,
    topics: list[str] | None = None,
) -> RawIntelItem:
    return RawIntelItem(
        item_id=item_id,
        source_name=source,
        source_uri=f"https://example.test/{item_id}",
        title=title,
        summary="LLM security intelligence",
        published_at=NOW,
        fetched_at=NOW,
        relevance_score=relevance,
        metadata={"topics": topics or []},
    )


def test_dashboard_aggregates_coverage_quality_and_emerging_topics():
    items = [
        _item(
            "arxiv:one",
            "arxiv_api",
            title="CVE-2026-12345 prompt injection analysis",
            topics=["prompt injection"],
        ),
        _item(
            "nvd:cve-2026-12345",
            "nvd_cve_api",
            title="CVE-2026-12345 prompt injection",
            topics=["prompt injection"],
        ),
        _item(
            "nvd:noise",
            "nvd_cve_api",
            title="unrelated record",
            relevance=0.1,
        ),
    ]
    board = IntelRunBlackboard(run_id="run-1", run_goal="test")
    board.query_outcomes.append(
        QueryCallOutcome(
            call_id="call-1",
            source_name="nvd_cve_api",
            query_text="prompt injection",
            evidence_channel="vulnerability_advisory",
            raw_count=3,
            in_scope_count=3,
            duplicate_count=1,
            new_count=2,
            relevant_new=1,
            noise_count=1,
            latency_ms=120,
            reward=0.25,
        )
    )
    board.candidate_topics.append(
        CandidateTopic(
            candidate_id="candidate:one",
            proposed_name="emerging trust attack",
            supporting_item_ids=["a", "b", "c"],
            source_names=["arxiv_api", "nvd_cve_api"],
            mean_relevance=0.8,
            emergence_score=0.6,
            metadata={
                "independent_evidence_count": 3,
                "recent_30d": 2,
                "burst_ratio": 2.0,
            },
        )
    )

    data = build_dashboard_data(items, [board], now=NOW)

    assert data["kpis"]["effective_items"] == 2
    assert data["kpis"]["corroboration_rate"] == 1.0
    assert len(data["gaps"]) == 34  # 18 research + 16 vulnerability/advisory targets
    assert data["topic_counts"]["prompt injection"] == 2
    nvd = next(row for row in data["source_rows"] if row[0] == "nvd_cve_api")
    assert nvd[3:] == [1, 100.0, 1.0, 66.7, 33.3, 50.0, 120.0, 0.25]
    assert data["candidate_rows"][0][:3] == ["emerging trust attack", "proposed", 0.6]


def test_dashboard_handles_empty_corpus_without_division_errors():
    data = build_dashboard_data([], [], now=NOW)

    assert data["kpis"]["effective_items"] == 0
    assert data["kpis"]["coverage_index"] == 0.0
    assert data["kpis"]["corroboration_rate"] == 0.0
    assert len(data["gap_rows"]) == 34
    assert data["source_rows"] == []


def test_refresh_dashboard_reports_store_failure(monkeypatch):
    class BrokenStore:
        def store_backend(self):
            return "broken"

        def load_corpus_items(self):
            raise RuntimeError("offline")

    monkeypatch.setattr("console.intel_dashboard.default_store", lambda: BrokenStore())

    outputs = refresh_intel_dashboard()

    assert len(outputs) == 10
    assert "RuntimeError: offline" in outputs[0]
    assert outputs[3] == []
    assert outputs[9] == []
