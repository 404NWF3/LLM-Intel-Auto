from __future__ import annotations

import sys
import time
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime
SourceScheduler = import_module(
    "agents.intel_agents.services.source_scheduler"
).SourceScheduler
RegisteredSourceDTO = import_module(
    "agents.intel_agents.schemas.source"
).RegisteredSourceDTO
SourceExecutionPlanDTO = import_module(
    "agents.intel_agents.schemas.plan"
).SourceExecutionPlanDTO
SourceFetchBatchDTO = import_module(
    "agents.intel_agents.schemas.source"
).SourceFetchBatchDTO
SourceFetchedItemDTO = import_module(
    "agents.intel_agents.schemas.source"
).SourceFetchedItemDTO
CrewCollaborationService = import_module(
    "agents.intel_agents.crews.crew_collaboration"
).CrewCollaborationService


class SlowToolbox:
    def fetch(self, source, query_run, *, runtime_mode, timeout, cursor_state):
        time.sleep(0.2)
        return SourceFetchBatchDTO(
            query_run=query_run,
            items=[
                SourceFetchedItemDTO(
                    source_name=source.source_name,
                    source_uri=f"stub://{source.source_name}/{query_run.query_run_id}",
                    external_id=query_run.query_run_id,
                    title=f"Stub {source.source_name}",
                    summary="parallel test",
                    raw_format="json",
                    payload='{"ok": true}',
                )
            ],
            fetched_at="2026-01-01T00:00:00+00:00",
            latency_ms=200.0,
            attempt_count=1,
            success=True,
            used_stub=True,
        )


class TracingToolbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None, float]] = []

    def fetch(self, source, query_run, *, runtime_mode, timeout, cursor_state):
        started = time.perf_counter()
        self.calls.append(
            (
                source.source_name,
                query_run.query_text,
                (cursor_state or {}).get("cursor"),
                started,
            )
        )
        time.sleep(0.1)
        return SourceFetchBatchDTO(
            query_run=query_run,
            items=[
                SourceFetchedItemDTO(
                    source_name=source.source_name,
                    source_uri=f"stub://{source.source_name}/{query_run.query_run_id}",
                    external_id=query_run.query_run_id,
                    title=f"Stub {source.source_name}",
                    summary="parallel test",
                    raw_format="json",
                    payload='{"ok": true}',
                )
            ],
            fetched_at="2026-01-01T00:00:00+00:00",
            latency_ms=100.0,
            attempt_count=1,
            success=True,
            used_stub=True,
            next_cursor=f"cursor_{query_run.query_text.replace(' ', '_')}",
        )


def test_phase1_runtime_records_collection_coordination() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run()

    assert result["collection_coordination"] is not None
    assert result["collection_coordination"]["collector_agents"]
    assert result["collection_coordination"]["assignments"]
    assert result["collection_coordination"]["engine"] in {"fallback", "crewai"}
    assert result["raw_items"][0]["metadata"]["collector_agent"]
    assert result["raw_items"][0]["metadata"]["execution_notes"]
    assert result["collection_coordination"]["collector_agents"][0]["execution_hints"]


def test_source_scheduler_parallelizes_across_sources() -> None:
    scheduler = SourceScheduler(toolbox=SlowToolbox())
    registry = [
        RegisteredSourceDTO(
            source_name="nvd",
            source_type="structured",
            base_uri="stub://nvd",
            adapter_name="nvd",
        ),
        RegisteredSourceDTO(
            source_name="arxiv",
            source_type="paper",
            base_uri="stub://arxiv",
            adapter_name="arxiv",
        ),
        RegisteredSourceDTO(
            source_name="reddit",
            source_type="community",
            base_uri="stub://reddit",
            adapter_name="reddit",
        ),
    ]
    plans = [
        SourceExecutionPlanDTO(
            source_name=item.source_name,
            source_type=item.source_type,
            priority=1.0,
            queries=[f"query {item.source_name}"],
            query_intent="broad_recall",
            query_provenance="test",
            rewrite_reason=None,
            max_results=1,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python")
        for item in registry
    ]

    started = time.perf_counter()
    result = scheduler.run(
        plans,
        registry=registry,
        trace_id="trace_parallel_test",
        run_mode="bootstrap",
        reflection_round=0,
        runtime_mode="stub",
        retry_attempts=1,
        request_timeout_seconds=5.0,
        max_parallel_sources=3,
        source_cursors={},
        assignment_map={
            item.source_name: {
                "execution_profile": "broad_discovery",
                "source_specific_hint": "Cast a broad but source-aware recall net.",
            }
            for item in registry
        },
    )
    elapsed = time.perf_counter() - started

    assert len(result["fetch_batches"]) == 3
    assert elapsed < 0.45
    assert result["source_execution_stats"][0]["execution_profile"] == "broad_discovery"
    assert result["source_execution_stats"][0]["source_specific_hint"]


def test_crewai_collaboration_service_falls_back_cleanly() -> None:
    service = CrewCollaborationService()
    result = service.coordinate(
        [
            {
                "source_name": "nvd",
                "source_type": "structured",
                "queries": ["prompt injection"],
                "query_intent": "broad_recall",
                "priority": 1.0,
            }
        ],
        run_mode="bootstrap",
        trace_id="trace_crew_test",
        planning_audits=[{"strategy_executed": "rules_only"}],
        reflection_audits=[{"diagnosis": "high_noise"}],
    )

    assert result["assignments"]
    assert result["collector_agents"]
    assert result["engine"] in {"fallback", "crewai"}
    assert result["assignments"][0]["execution_notes"]
    assert result["assignments"][0]["planning_signal"] == "rules_only"
    assert result["assignments"][0]["reflection_signal"] == "high_noise"


def test_source_scheduler_serializes_same_source_queries() -> None:
    toolbox = TracingToolbox()
    scheduler = SourceScheduler(toolbox=toolbox)
    registry = [
        RegisteredSourceDTO(
            source_name="reddit",
            source_type="community",
            base_uri="stub://reddit",
            adapter_name="reddit",
        ),
        RegisteredSourceDTO(
            source_name="arxiv",
            source_type="paper",
            base_uri="stub://arxiv",
            adapter_name="arxiv",
        ),
    ]
    plans = [
        SourceExecutionPlanDTO(
            source_name="reddit",
            source_type="community",
            priority=1.0,
            queries=["query reddit 1", "query reddit 2"],
            query_intent="weak_signal_probe",
            query_provenance="test",
            rewrite_reason=None,
            max_results=1,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python"),
        SourceExecutionPlanDTO(
            source_name="arxiv",
            source_type="paper",
            priority=0.9,
            queries=["query arxiv"],
            query_intent="evidence_corroboration",
            query_provenance="test",
            rewrite_reason=None,
            max_results=1,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python"),
    ]

    result = scheduler.run(
        plans,
        registry=registry,
        trace_id="trace_same_source_test",
        run_mode="bootstrap",
        reflection_round=0,
        runtime_mode="stub",
        retry_attempts=1,
        request_timeout_seconds=5.0,
        max_parallel_sources=2,
        source_cursors={"reddit": {"cursor": "cursor0"}},
    )

    assert len(result["fetch_batches"]) == 3
    reddit_calls = [row for row in toolbox.calls if row[0] == "reddit"]
    assert len(reddit_calls) == 2
    # A legacy shared cursor cannot safely seed two distinct queries.
    assert reddit_calls[0][2] is None
    assert reddit_calls[1][2] is None
    assert reddit_calls[1][3] >= reddit_calls[0][3]
    # Stub responses must not advance live checkpoints.
    assert result["source_cursors"] == {"reddit": {"cursor": "cursor0"}}
