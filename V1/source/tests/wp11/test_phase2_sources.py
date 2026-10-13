from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

SourceCollectionCrew = import_module(
    "agents.intel_agents.crews.source_collection_crew"
).SourceCollectionCrew
CollectionPlanDTO = import_module("agents.intel_agents.schemas.plan").CollectionPlanDTO
SourceExecutionPlanDTO = import_module(
    "agents.intel_agents.schemas.plan"
).SourceExecutionPlanDTO
RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO
RawIngestFlow = import_module(
    "agents.intel_agents.services.raw_ingest_flow"
).RawIngestFlow
SourceRegistryService = import_module(
    "agents.intel_agents.services.source_registry"
).SourceRegistryService
SourceFetchToolbox = import_module(
    "agents.intel_agents.tools.source_fetch_tools"
).SourceFetchToolbox
QueryRunDTO = import_module("agents.intel_agents.schemas.source").QueryRunDTO
RegisteredSourceDTO = import_module(
    "agents.intel_agents.schemas.source"
).RegisteredSourceDTO


def test_phase2_registry_contains_first_wave_sources() -> None:
    registry = SourceRegistryService().get_enabled_sources()
    names = {item.source_name for item in registry}
    assert {
        "nvd",
        "github_advisories",
        "arxiv",
        "reddit",
        "hackernews",
        "cisa_kev",
        "mitre_attack",
    }.issubset(names)


def test_phase2_collection_creates_unified_raw_items(tmp_path: Path) -> None:
    context = RuntimeContextDTO.default_stub().model_dump(mode="python")
    context["artifact_store_dir"] = str(tmp_path / "artifacts")
    plans = [
        SourceExecutionPlanDTO(
            source_name="nvd",
            source_type="structured",
            priority=1.0,
            queries=["prompt injection"],
            query_intent="broad_recall",
            query_provenance="test",
            rewrite_reason=None,
            max_results=5,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python"),
        SourceExecutionPlanDTO(
            source_name="arxiv",
            source_type="paper",
            priority=0.9,
            queries=["jailbreak language model"],
            query_intent="broad_recall",
            query_provenance="test",
            rewrite_reason=None,
            max_results=5,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python"),
    ]

    result = SourceCollectionCrew().collect(
        plans,
        trace_id="trace_test_phase2",
        run_mode="bootstrap",
        reflection_round=0,
        runtime_mode="stub",
        retry_attempts=2,
        request_timeout_seconds=5.0,
        artifact_store_dir=context["artifact_store_dir"],
        source_cursors={},
    )

    assert len(result["raw_items"]) == 2
    assert len(result["source_execution_stats"]) == 2
    assert len(result["fetch_audits"]) == 2
    assert all(Path(item["payload_uri"]).exists() for item in result["raw_items"])
    assert all(item["query_run_id"] for item in result["raw_items"])


def test_phase2_local_ingest_writes_manifest(tmp_path: Path) -> None:
    flow = RawIngestFlow(str(tmp_path / "raw_records"))
    raw_items = [
        {
            "query_run_id": "qrun_test_1",
            "source_name": "nvd",
            "source_uri": "stub://nvd/1",
            "external_id": "CVE-STUB-1",
            "title": "Stub CVE",
            "summary": "Stub summary",
            "author": None,
            "published_at": "2026-01-01T00:00:00+00:00",
            "fetched_at": "2026-01-01T00:00:01+00:00",
            "raw_format": "json",
            "artifact_ref": str(tmp_path / "artifact.json"),
            "payload_uri": str(tmp_path / "artifact.json"),
            "language_code": "en",
            "relevance_score": 0.9,
            "parser_status": "pending",
            "metadata": {"query_text": "prompt injection"},
            "content_hash": "a" * 64,
        }
    ]

    stored, audits = flow.ingest(
        raw_items, run_id="run_test_phase2", trace_id="trace_test_phase2"
    )

    assert len(stored) == 1
    assert len(audits) == 1
    assert stored[0]["stored_via"] == "local_manifest"
    manifest_path = (
        tmp_path / "raw_records" / "run_test_phase2" / f"{stored[0]['raw_id']}.json"
    )
    assert manifest_path.exists()


def test_phase2_stub_fetch_records_intent_aware_query_metadata() -> None:
    toolbox = SourceFetchToolbox()
    source = RegisteredSourceDTO(
        source_name="reddit",
        source_type="community",
        base_uri="stub://reddit",
        adapter_name="reddit",
    )
    query_run = QueryRunDTO(
        query_run_id="qrun_intent_1",
        source_name="reddit",
        query_text="llm jailbreak",
        query_intent="weak_signal_probe",
        reflection_round=0,
        max_results=5,
        time_window_days=7,
        trace_id="trace_phase2_intent",
        run_mode="bootstrap",
    )

    batch = toolbox.fetch(
        source,
        query_run,
        runtime_mode="stub",
        timeout=5.0,
        cursor_state={},
    )

    assert batch.request_audit["request_meta"]["query_intent"] == "weak_signal_probe"
    assert (
        batch.request_audit["request_meta"]["transformed_query_text"] != "llm jailbreak"
    )
    assert batch.request_audit["request_meta"]["request_profile"] == "reddit_rss_search"
    assert (
        batch.items[0].metadata["transformed_query_text"]
        == batch.request_audit["request_meta"]["transformed_query_text"]
    )


def test_phase2_intent_aware_query_builder_varies_by_source() -> None:
    toolbox = SourceFetchToolbox()
    nvd_plan = toolbox._intent_aware_request_plan(
        RegisteredSourceDTO(
            source_name="nvd",
            source_type="structured",
            base_uri="stub://nvd",
            adapter_name="nvd",
        ),
        QueryRunDTO(
            query_run_id="qrun_nvd_1",
            source_name="nvd",
            query_text="langchain prompt injection",
            query_intent="precision_probe",
            reflection_round=0,
            max_results=5,
            time_window_days=7,
            trace_id="trace_nvd",
            run_mode="bootstrap",
        ),
    )
    arxiv_plan = toolbox._intent_aware_request_plan(
        RegisteredSourceDTO(
            source_name="arxiv",
            source_type="paper",
            base_uri="stub://arxiv",
            adapter_name="arxiv",
        ),
        QueryRunDTO(
            query_run_id="qrun_arxiv_1",
            source_name="arxiv",
            query_text="prompt injection language model",
            query_intent="evidence_corroboration",
            reflection_round=0,
            max_results=5,
            time_window_days=30,
            trace_id="trace_arxiv",
            run_mode="bootstrap",
        ),
    )
    kev_plan = toolbox._intent_aware_request_plan(
        RegisteredSourceDTO(
            source_name="cisa_kev",
            source_type="advisory",
            base_uri="stub://kev",
            adapter_name="cisa_kev",
        ),
        QueryRunDTO(
            query_run_id="qrun_kev_1",
            source_name="cisa_kev",
            query_text="agent hijack",
            query_intent="taxonomy_anchor",
            reflection_round=0,
            max_results=5,
            time_window_days=7,
            trace_id="trace_kev",
            run_mode="bootstrap",
        ),
    )

    assert "vulnerability exploit" in nvd_plan["query_text"]
    assert arxiv_plan["sort_by"] == "relevance"
    assert "attack" in kev_plan["query_text"]
