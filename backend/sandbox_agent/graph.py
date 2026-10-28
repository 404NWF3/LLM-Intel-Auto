"""Export persisted intelligence as a reproducible GraphRAG corpus."""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class GraphBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    limit: int = Field(default=100, ge=2, le=2000)
    focus: str = Field(default="", max_length=200)


def export_corpus(store, config: GraphBuildRequest):
    items = store.load_corpus_items()
    unique = {item.item_id: item for item in items}
    eligible = [item for item in unique.values() if item.summary.strip()]
    if config.focus:
        needle = config.focus.casefold()
        eligible = [
            item
            for item in eligible
            if needle
            in f"{item.title} {item.summary} {json.dumps(item.metadata, ensure_ascii=False)}".casefold()
        ]
    eligible.sort(
        key=lambda item: (
            item.relevance_score,
            (item.published_at or item.fetched_at).isoformat(),
            item.item_id,
        ),
        reverse=True,
    )
    selected = eligible[: config.limit]
    if len(selected) < 2:
        raise HTTPException(
            422, "至少需要两条有摘要的匹配情报，请调整范围或先运行情报采集。"
        )
    documents, sources = [], []
    for item in selected:
        identifier = "intel-" + hashlib.sha256(item.item_id.encode()).hexdigest()[:24]
        text = f"Title: {item.title}\nIntelligence ID: {item.item_id}\nSource: {item.source_name}\nURL: {item.source_uri}\n\nSummary:\n{item.summary[:6000]}"
        documents.append(
            {"id": identifier, "title": item.title or item.item_id, "text": text}
        )
        sources.append(
            {
                "document_id": identifier,
                "item_id": item.item_id,
                "title": item.title,
                "source_name": item.source_name,
                "source_uri": item.source_uri,
                "published_at": item.published_at.isoformat()
                if item.published_at
                else None,
                "relevance_score": item.relevance_score,
                "summary_truncated": len(item.summary) > 6000,
            }
        )
    digest = hashlib.sha256(
        json.dumps(documents, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": digest,
        "available_items": len(unique),
        "matching_items": len(eligible),
        "indexed_items": len(documents),
        "selection": config.model_dump(),
        "source_field": "title + summary (maximum 6000 characters) + source metadata",
        "sources": sources,
    }
    return documents, manifest
