"""File-backed store for intel_agent runs.

Writes ``data/intel_runs/<run_id>.json`` + ``latest.json`` in a layout that the
legacy Gradio console can still read (extra keys tolerated), while carrying no
import dependency on the legacy package. KG bookkeeping is intentionally
dropped: the intel_agent engine does not generate knowledge graphs.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import IntelRunBlackboard, RawIntelItem, RawIntelItemBatch, SourceCheckpoint
from .content import merge_item_documents
from .topics import EXTENDED_SECURITY_TOPICS

DEFAULT_INTEL_RUN_DIR = Path("data") / "intel_runs"
LATEST_INDEX_NAME = "latest.json"


class JsonIntelRunStore:
    def __init__(
        self,
        root_dir: str | Path = DEFAULT_INTEL_RUN_DIR,
    ) -> None:
        self.root_dir = Path(root_dir)
        self._payload_cache: dict[Path, tuple[tuple[int, int], dict[str, Any]]] = {}
        self._items_cache: tuple[tuple, dict[str, dict[str, Any]]] | None = None

    def _read_payload(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        cached = self._payload_cache.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._payload_cache[path] = (stamp, payload)
        return payload

    def run_path(self, run_id: str) -> Path:
        return self.root_dir / f"{_safe_run_id(run_id)}.json"

    def latest_index_path(self) -> Path:
        return self.root_dir / LATEST_INDEX_NAME

    def save_run(
        self,
        blackboard: IntelRunBlackboard,
        raw_item_batches: list[RawIntelItemBatch] | None = None,
        status: str = "succeeded",
    ) -> Path:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        saved_at = _utcnow_iso()
        existing = {doc["item_id"]: doc for doc in self.query_items(limit=100_000)}
        blackboard = blackboard.model_copy(deep=True)
        merged = []
        for item in blackboard.raw_items:
            doc = item.model_dump(mode="json")
            doc.setdefault("last_run_id", blackboard.run_id)
            doc.setdefault("last_seen_at", saved_at)
            merged.append(RawIntelItem.model_validate(merge_item_documents(doc, existing.get(item.item_id, {}))))
        blackboard.raw_items = merged
        path = self.run_path(blackboard.run_id)
        payload = {
            "schema_version": 3,
            "run_id": blackboard.run_id,
            "status": status,
            "saved_at": saved_at,
            "engine": "intel_agent",
            "summary": self._summary(blackboard, raw_item_batches or []),
            "raw_item_batches": [b.model_dump(mode="json") for b in raw_item_batches or []],
            "blackboard": blackboard.model_dump(mode="json"),
        }
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

        self.latest_index_path().write_text(
            json.dumps(
                {
                    "run_id": blackboard.run_id,
                    "status": status,
                    "path": path.name,
                    "saved_at": saved_at,
                    "raw_items": len(blackboard.raw_items),
                    "rounds": len(blackboard.query_history),
                },
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def load_run_payload(self, run_id: str) -> dict[str, Any]:
        return deepcopy(self._read_payload(self.run_path(run_id)))

    def load_latest_payload(self) -> dict[str, Any] | None:
        index_path = self.latest_index_path()
        if not index_path.exists():
            return None
        index = json.loads(index_path.read_text(encoding="utf-8"))
        name = index.get("path")
        if not name:
            return None
        path = self.root_dir / str(name)
        return deepcopy(self._read_payload(path)) if path.exists() else None

    def list_run_paths(self, limit: int | None = 20) -> list[Path]:
        if not self.root_dir.exists():
            return []
        paths = [p for p in self.root_dir.glob("*.json") if p.name != LATEST_INDEX_NAME]
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return paths[:limit]

    def load_all_blackboards(self, limit: int = 200) -> list[IntelRunBlackboard]:
        boards: list[IntelRunBlackboard] = []
        for path in self.list_run_paths(limit=limit):
            try:
                payload = self._read_payload(path)
                boards.append(IntelRunBlackboard.model_validate(payload["blackboard"]))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
        return boards

    def load_corpus_items(self) -> list[RawIntelItem]:
        """Load the complete JSON corpus once, de-duplicated by natural item id."""
        items = []
        for doc in self.query_items(limit=100_000):
            try:
                items.append(RawIntelItem.model_validate(doc))
            except ValueError:
                continue
        return items

    def load_source_checkpoints(self) -> list[SourceCheckpoint]:
        latest: dict[str, SourceCheckpoint] = {}
        for blackboard in self.load_all_blackboards(limit=100_000):
            for checkpoint in blackboard.source_checkpoints:
                latest.setdefault(checkpoint.source_name, checkpoint)
        return list(latest.values())

    def format_latest_intel(self, limit: int = 20) -> str:
        payload = self.load_latest_payload()
        if not payload:
            return f"No persisted intelligence runs found in {self.root_dir}."
        blackboard = IntelRunBlackboard.model_validate(payload["blackboard"])
        items = sorted(
            blackboard.raw_items,
            key=lambda item: item.published_at or item.fetched_at,
            reverse=True,
        )[:limit]
        lines = [
            f"Latest run: {payload['run_id']}",
            f"Status: {payload.get('status', 'unknown')}",
            f"Saved at: {payload.get('saved_at', 'unknown')}",
            "",
            format_intel_items(items),
        ]
        return "\n".join(lines).rstrip()

    def store_backend(self) -> str:
        return f"json:{self.root_dir}"

    def run_count(self) -> int:
        return len(self.list_run_paths(limit=None))

    def distinct_item_count(self) -> int:
        return len(self.query_items(limit=None))

    def list_run_summaries(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.list_run_paths(limit=limit):
            try:
                payload = self._read_payload(path)
            except (OSError, json.JSONDecodeError):
                continue
            summary = payload.get("summary") or {}
            bb = payload.get("blackboard") or {}
            rows.append(
                {
                    "run_id": payload.get("run_id"),
                    "status": payload.get("status"),
                    "saved_at": payload.get("saved_at"),
                    "item_count": summary.get("raw_items", len(bb.get("raw_items") or [])),
                    "run_mode": summary.get("run_mode") or bb.get("run_mode"),
                    "rounds": summary.get("rounds", len(bb.get("query_history") or [])),
                    "run_goal": summary.get("run_goal") or bb.get("run_goal"),
                    "coverage_gaps": ", ".join(summary.get("coverage_gaps_remaining") or []),
                    "stop_reason": summary.get("stop_reason"),
                    "core_gap_count": summary.get("core_gap_count", 0),
                    "extended_item_count": summary.get("extended_item_count", 0),
                    "candidate_topic_count": summary.get("candidate_topic_count", 0),
                    "engine": payload.get("engine"),
                }
            )
        return rows

    def query_items(
        self,
        *,
        source_name: str | None = None,
        topic: str | None = None,
        text: str | None = None,
        run_id: str | None = None,
        limit: int | None = 200,
    ) -> list[dict[str, Any]]:
        """Flatten run files, deduplicating by item_id; None exports all items."""
        source = (source_name or "").strip().lower()
        topic_f = (topic or "").strip().lower()
        needle = (text or "").strip().lower()
        run_f = (run_id or "").strip()
        paths = self.list_run_paths(limit=None)
        signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
        if self._items_cache and self._items_cache[0] == signature:
            by_id = self._items_cache[1]
            paths = []
        else:
            by_id: dict[str, dict[str, Any]] = {}
            def saved_at(path: Path) -> str:
                try:
                    return self._read_payload(path).get("saved_at") or ""
                except (OSError, json.JSONDecodeError):
                    return ""
            paths = sorted(paths, key=saved_at, reverse=True)
        for path in paths:
            try:
                payload = self._read_payload(path)
            except (OSError, json.JSONDecodeError):
                continue
            rid = str(payload.get("run_id") or "")
            for raw in (payload.get("blackboard") or {}).get("raw_items") or []:
                item_id = str(raw.get("item_id") or "")
                if not item_id:
                    continue
                topics = list((raw.get("metadata") or {}).get("topics") or [])
                doc = {
                    **raw,
                    "item_id": item_id,
                    "topics": topics,
                    "run_ids": list(dict.fromkeys([*(raw.get("run_ids") or []), *([rid] if rid else [])])),
                    "last_run_id": raw.get("last_run_id") or rid or None,
                    "last_seen_at": raw.get("last_seen_at") or payload.get("saved_at"),
                    "first_run_id": raw.get("first_run_id") or rid or None,
                    "first_seen_at": raw.get("first_seen_at") or payload.get("saved_at"),
                }
                if item_id in by_id:
                    by_id[item_id] = merge_item_documents(by_id[item_id], doc)
                else:
                    by_id[item_id] = doc

        self._items_cache = (signature, by_id)
        rows: list[dict[str, Any]] = []
        for doc in by_id.values():
            if run_f and run_f not in doc.get("run_ids", []):
                continue
            if source and str(doc.get("source_name") or "").lower() != source:
                continue
            topics = [str(t).lower() for t in (doc.get("topics") or [])]
            if topic_f and topic_f not in topics:
                continue
            if needle:
                blob = " ".join(
                    [
                        str(doc.get("item_id") or ""),
                        str(doc.get("title") or ""),
                        str(doc.get("summary") or ""),
                    ]
                ).lower()
                if needle not in blob:
                    continue
            rows.append(deepcopy(doc))
            if limit is not None and len(rows) >= max(1, int(limit)):
                break
        return rows

    def distinct_sources(self) -> list[str]:
        sources: set[str] = set()
        for doc in self.query_items(limit=10_000):
            name = doc.get("source_name")
            if name:
                sources.add(str(name))
        return sorted(sources)

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        for doc in self.query_items(text=item_id, limit=100_000):
            if str(doc.get("item_id") or doc.get("_id")) == item_id:
                return doc
        return None

    def update_item_texts(self, updates: dict[str, dict[str, Any]]) -> int:
        """Patch every persisted occurrence without changing run status/timestamps."""
        changed: set[str] = set()
        for path in self.list_run_paths(limit=100_000):
            payload = deepcopy(self._read_payload(path))
            rows = list((payload.get("blackboard") or {}).get("raw_items") or [])
            for batch in payload.get("raw_item_batches") or []:
                rows.extend(batch.get("items") or [])
            dirty = False
            for row in rows:
                patch = updates.get(row.get("item_id"))
                if patch:
                    row.update({key: value for key, value in patch.items() if key != "metadata"})
                    row.setdefault("metadata", {}).update(patch.get("metadata", {}))
                    dirty = True
                    changed.add(row["item_id"])
            if dirty:
                temporary = path.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(path)
        return len(changed)

    def _summary(
        self, blackboard: IntelRunBlackboard, batches: list[RawIntelItemBatch]
    ) -> dict[str, Any]:
        return {
            "run_goal": blackboard.run_goal,
            "run_mode": blackboard.run_mode,
            "rounds": len(blackboard.query_history),
            "raw_items": len(blackboard.raw_items),
            "raw_item_batches": len(batches),
            "coverage_gaps_remaining": [
                gap.taxonomy_or_component for gap in blackboard.coverage_gaps
            ],
            "stop_reason": blackboard.stop_reason,
            "core_gap_count": sum(1 for gap in blackboard.corpus_gaps if gap.status == "open"),
            "extended_item_count": sum(
                1
                for item in blackboard.raw_items
                if set(item.metadata.get("topics") or []) & set(EXTENDED_SECURITY_TOPICS)
            ),
            "candidate_topic_count": len(blackboard.candidate_topics),
            "last_action": (
                blackboard.action_history[-1].action_type
                if blackboard.action_history else None
            ),
        }


def format_intel_items(items: list[RawIntelItem]) -> str:
    if not items:
        return "No raw intelligence items found."
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        topics = ", ".join(item.metadata.get("topics", [])) or "unclassified"
        published = item.published_at.isoformat() if item.published_at else "unknown date"
        lines.append(
            "\n".join([
                f"{index}. {item.title or '(untitled)'}",
                f"   source: {item.source_name}",
                f"   published: {published}",
                f"   relevance: {item.relevance_score:.2f}",
                f"   topics: {topics}",
                f"   uri: {item.source_uri}",
            ])
        )
    return "\n\n".join(lines)


def _safe_run_id(run_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", run_id).strip("._") or "intel_run"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
