"""Gradio Knowledge Graphs panel: env-based GLM config, DB items, Mongo persist."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

import gradio as gr

from ctinexus_kg import (
    CtinexusKgGenerator,
    ItemKnowledgeGraphRecord,
    KgEligibilityDecision,
    KgGenerationConfig,
    generate_for_item,
    list_kg_ready,
)
from ctinexus_kg.topics import ALL_SECURITY_TOPICS
from intel_agent.store import default_store

from .db_browser import _write_csv

KG_RECORD_HEADERS = [
    "item_id",
    "run_id",
    "status",
    "source_name",
    "triplet_count",
    "entity_count",
    "model",
    "embedding_model",
    "saved_at",
    "error",
    "ctinexus_json_path",
]

BULK_POLICY_CHOICES = [
    ("跳过成功项，重试失败项（推荐）", "retry_failed"),
    ("仅生成从未处理项", "missing_only"),
    ("全部重新生成", "regenerate_all"),
]
BULK_POLICY_VALUES = {value for _, value in BULK_POLICY_CHOICES}
BULK_MAX_SCAN = 10_000
BULK_MAX_GENERATE = 1_000
BULK_RECENT_ROWS = 100


def default_kg_config() -> KgGenerationConfig:
    return KgGenerationConfig.from_env()


def kg_config_summary() -> str:
    cfg = default_kg_config()
    return (
        f"model={cfg.model} · embedding={cfg.embedding_model} · "
        f"base_url={cfg.base_url or '(from CTINEXUS_/GLM_/OPENAI_ env)'} · "
        f"threshold={cfg.similarity_threshold}"
    )


def _persist_record(record: Any) -> None:
    store = default_store()
    payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
    graph: dict[str, Any] | None = None
    path = payload.get("ctinexus_json_path")
    if path and Path(path).is_file():
        try:
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                graph = loaded
        except (OSError, json.JSONDecodeError):
            graph = None
    if hasattr(store, "save_knowledge_graph"):
        store.save_knowledge_graph(payload, graph)


def _run_id_for_item(item: dict[str, Any], fallback: str = "db-kg") -> str:
    run_ids = item.get("run_ids") or []
    first_from_list = run_ids[0] if run_ids else None
    return str(
        item.get("last_run_id")
        or item.get("first_run_id")
        or first_from_list
        or fallback
    )


def _kg_table(records: list[Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for r in records:
        if hasattr(r, "model_dump"):
            d = r.model_dump(mode="json")
        else:
            d = dict(r)
        excluded = ""
        elig = d.get("eligibility")
        if isinstance(elig, dict):
            excluded = elig.get("excluded_reason") or ""
        rows.append(
            [
                d.get("item_id"),
                d.get("status"),
                d.get("triplet_count", 0),
                d.get("entity_count", 0),
                excluded,
                d.get("error") or "",
                d.get("ctinexus_json_path") or "",
            ]
        )
    return rows


def refresh_db_ready(
    run_id: str = "",
    topic: str = "",
    source: str = "",
    limit: float | int = 100,
):
    store = default_store()
    cfg = default_kg_config()
    docs = store.query_items(
        source_name=source or None,
        topic=topic or None,
        run_id=run_id or None,
        limit=int(limit or 100),
    )
    ready = list_kg_ready(docs, config=cfg, target_topics=list(ALL_SECURITY_TOPICS))
    choices = [i.item_id for i in ready]
    msg = (
        f"{len(choices)} kg_ready of {len(docs)} queried "
        f"(config: {cfg.model} / {cfg.embedding_model})"
    )
    return msg, gr.update(choices=choices, value=choices[0] if choices else None)


def generate_selected_from_db(item_id: str) -> tuple[str, list[list[Any]]]:
    iid = (item_id or "").strip()
    if not iid:
        return "Select a kg_ready item_id.", []
    store = default_store()
    match = None
    if hasattr(store, "get_item"):
        match = store.get_item(iid)
    if match is None:
        for d in store.query_items(limit=5000):
            if str(d.get("item_id") or d.get("_id")) == iid:
                match = d
                break
    if match is None:
        return f"Item {iid!r} not found in store.", []

    cfg = default_kg_config()
    run_id = _run_id_for_item(match)
    record = generate_for_item(run_id, match, config=cfg)
    try:
        _persist_record(record)
    except Exception as exc:  # noqa: BLE001
        return (
            json.dumps(
                {
                    "warning": f"KG generated but persist failed: {exc}",
                    "record": record.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            _kg_table([record]),
        )
    return (
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        _kg_table([record]),
    )


def generate_batch_from_db(
    run_id: str = "",
    topic: str = "",
    source: str = "",
    limit: float | int = 20,
) -> tuple[str, list[list[Any]]]:
    store = default_store()
    cfg = default_kg_config()
    docs = store.query_items(
        source_name=source or None,
        topic=topic or None,
        run_id=run_id or None,
        limit=int(limit or 20),
    )
    ready = list_kg_ready(docs, config=cfg, target_topics=list(ALL_SECURITY_TOPICS))
    if not ready:
        return "No kg_ready items for the current filters.", []

    records = []
    for item in ready:
        rid = _run_id_for_item(item.model_dump(mode="json"))
        rec = generate_for_item(rid, item, config=cfg)
        try:
            _persist_record(rec)
        except Exception as exc:  # noqa: BLE001
            rec.error = f"{rec.error or ''}; persist failed: {exc}".strip("; ")
        records.append(rec)

    summary = {
        "attempted": len(records),
        "succeeded": sum(1 for r in records if r.status == "succeeded"),
        "failed": sum(1 for r in records if r.status == "failed"),
        "skipped": sum(1 for r in records if r.status == "skipped"),
        "config": {"model": cfg.model, "embedding_model": cfg.embedding_model},
    }
    return json.dumps(summary, ensure_ascii=False, indent=2), _kg_table(records)


def _bounded_int(value: float | int, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    return max(1, min(parsed, maximum))


def _existing_kg_statuses(
    store: Any,
    docs: list[dict[str, Any]],
    lookup_limit: int,
) -> tuple[dict[str, str], str | None]:
    statuses = {
        str(doc.get("item_id") or doc.get("_id")): str(doc.get("kg_status"))
        for doc in docs
        if (doc.get("item_id") or doc.get("_id")) and doc.get("kg_status")
    }
    if not hasattr(store, "list_knowledge_graphs"):
        return statuses, None
    try:
        for record in store.list_knowledge_graphs(limit=lookup_limit):
            item_id = str(record.get("item_id") or record.get("_id") or "")
            if item_id and record.get("status"):
                statuses[item_id] = str(record["status"])
    except Exception as exc:  # noqa: BLE001 - item-level kg_status may still be usable
        return statuses, f"existing KG lookup failed: {exc.__class__.__name__}: {exc}"
    return statuses, None


def _should_generate(existing_status: str | None, policy: str) -> bool:
    if policy == "regenerate_all":
        return True
    if policy == "missing_only":
        return existing_status is None
    return existing_status != "succeeded"


def _unexpected_failure_record(
    item: Any,
    run_id: str,
    config: KgGenerationConfig,
    exc: Exception,
) -> ItemKnowledgeGraphRecord:
    return ItemKnowledgeGraphRecord(
        run_id=run_id,
        item_id=item.item_id,
        source_name=item.source_name,
        source_uri=item.source_uri,
        status="failed",
        eligibility=KgEligibilityDecision(
            item_id=item.item_id,
            eligible=True,
            reasons=["bulk generation raised before CTINexus produced a record"],
            matched_topics=list(item.metadata.get("topics") or []),
            relevance_score=item.relevance_score,
            source_name=item.source_name,
        ),
        matched_topics=list(item.metadata.get("topics") or []),
        relevance_score=item.relevance_score,
        provider=config.provider,
        model=config.model,
        embedding_model=config.embedding_model,
        similarity_threshold=config.similarity_threshold,
        error=f"{exc.__class__.__name__}: {exc}",
        metadata={"error_type": exc.__class__.__name__, "bulk_unexpected_failure": True},
    )


def _bulk_summary(
    *,
    status: str,
    scanned: int,
    ready: int,
    selected: int,
    skipped_existing: int,
    records: list[ItemKnowledgeGraphRecord],
    policy: str,
    config: KgGenerationConfig,
    current_item: str | None = None,
    warning: str | None = None,
) -> str:
    processed = len(records)
    payload = {
        "status": status,
        "scanned": scanned,
        "kg_ready": ready,
        "selected": selected,
        "skipped_existing": skipped_existing,
        "processed": processed,
        "remaining": max(0, selected - processed),
        "progress_percent": round(100.0 * processed / selected, 1) if selected else 100.0,
        "succeeded": sum(record.status == "succeeded" for record in records),
        "failed": sum(record.status == "failed" for record in records),
        "skipped": sum(record.status == "skipped" for record in records),
        "persist_failed": sum(
            bool(record.metadata.get("persist_failed")) for record in records
        ),
        "current_item": current_item,
        "policy": policy,
        "config": {"model": config.model, "embedding_model": config.embedding_model},
    }
    if warning:
        payload["warning"] = warning
    return json.dumps(payload, ensure_ascii=False, indent=2)


def generate_bulk_from_db(
    run_id: str = "",
    topic: str = "",
    source: str = "",
    scan_limit: float | int = 1_000,
    max_items: float | int = 100,
    existing_policy: str = "retry_failed",
) -> Iterator[tuple[str, list[list[Any]]]]:
    """Stream a resumable, sequential large-batch item-KG generation job."""
    store = default_store()
    config = default_kg_config()
    scan_count = _bounded_int(scan_limit, 1_000, BULK_MAX_SCAN)
    generate_count = _bounded_int(max_items, 100, BULK_MAX_GENERATE)
    policy = existing_policy if existing_policy in BULK_POLICY_VALUES else "retry_failed"

    try:
        docs = store.query_items(
            source_name=source or None,
            topic=topic or None,
            run_id=run_id or None,
            limit=scan_count,
        )
        ready = list_kg_ready(docs, config=config, target_topics=list(ALL_SECURITY_TOPICS))
    except Exception as exc:  # noqa: BLE001 - surface query/eligibility failures in the UI
        error = json.dumps(
            {
                "status": "failed",
                "error": f"{exc.__class__.__name__}: {exc}",
                "scanned": 0,
                "processed": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
        yield error, []
        return

    statuses, lookup_warning = _existing_kg_statuses(
        store,
        docs,
        lookup_limit=min(100_000, max(10_000, scan_count * 2)),
    )
    selected = [
        item for item in ready if _should_generate(statuses.get(item.item_id), policy)
    ][:generate_count]
    skipped_existing = sum(
        not _should_generate(statuses.get(item.item_id), policy) for item in ready
    )
    records: list[ItemKnowledgeGraphRecord] = []

    yield (
        _bulk_summary(
            status="running" if selected else "completed",
            scanned=len(docs),
            ready=len(ready),
            selected=len(selected),
            skipped_existing=skipped_existing,
            records=records,
            policy=policy,
            config=config,
            warning=lookup_warning,
        ),
        [],
    )
    if not selected:
        return

    generator = CtinexusKgGenerator(config=config)
    records_by_run: dict[str, list[ItemKnowledgeGraphRecord]] = defaultdict(list)
    try:
        for item in selected:
            item_payload = item.model_dump(mode="json")
            item_run_id = _run_id_for_item(item_payload)
            try:
                record = generator.generate_for_item(
                    item_run_id,
                    item,
                    target_topics=list(ALL_SECURITY_TOPICS),
                )
            except Exception as exc:  # noqa: BLE001 - one bad item must not stop the batch
                record = _unexpected_failure_record(item, item_run_id, config, exc)
            try:
                _persist_record(record)
            except Exception as exc:  # noqa: BLE001 - keep generated file and continue
                record.error = f"{record.error or ''}; persist failed: {exc}".strip("; ")
                record.metadata["persist_failed"] = True
                record.metadata["persist_error_type"] = exc.__class__.__name__
            records.append(record)
            records_by_run[item_run_id].append(record)
            yield (
                _bulk_summary(
                    status="running",
                    scanned=len(docs),
                    ready=len(ready),
                    selected=len(selected),
                    skipped_existing=skipped_existing,
                    records=records,
                    policy=policy,
                    config=config,
                    current_item=item.item_id,
                    warning=lookup_warning,
                ),
                _kg_table(records[-BULK_RECENT_ROWS:]),
            )
    finally:
        for item_run_id, run_records in records_by_run.items():
            try:
                generator.write_manifest(item_run_id, run_records)
            except Exception as exc:  # noqa: BLE001 - records are already persisted independently
                lookup_warning = (
                    f"{lookup_warning}; " if lookup_warning else ""
                ) + f"manifest write failed for {item_run_id}: {exc}"

    yield (
        _bulk_summary(
            status="completed",
            scanned=len(docs),
            ready=len(ready),
            selected=len(selected),
            skipped_existing=skipped_existing,
            records=records,
            policy=policy,
            config=config,
            warning=lookup_warning,
        ),
        _kg_table(records[-BULK_RECENT_ROWS:]),
    )


def list_kg_records(
    status: str = "",
    run_id: str = "",
    item_id: str = "",
    limit: float | int = 100,
) -> tuple[str, list[list[Any]], str | None]:
    store = default_store()
    if not hasattr(store, "list_knowledge_graphs"):
        return "Store does not support knowledge_graphs.", [], None
    docs = store.list_knowledge_graphs(
        status=status or None,
        run_id=run_id or None,
        item_id=item_id or None,
        limit=int(limit or 100),
    )
    rows = [
        [
            d.get("item_id"),
            d.get("run_id"),
            d.get("status"),
            d.get("source_name"),
            d.get("triplet_count", 0),
            d.get("entity_count", 0),
            d.get("model"),
            d.get("embedding_model"),
            d.get("saved_at"),
            d.get("error") or "",
            d.get("ctinexus_json_path") or "",
        ]
        for d in docs
    ]
    path = _write_csv(KG_RECORD_HEADERS, rows, "knowledge_graphs") if rows else None
    return f"{len(rows)} KG record(s)", rows, path
