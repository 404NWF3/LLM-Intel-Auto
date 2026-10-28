"""Repeatable CSV import and raw-text repair, with backups and audit reports."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from .content import merge_item_documents, preserve_text
from .persistence import JsonIntelRunStore
from .schemas import IntelRunBlackboard, RawIntelItem
from . import sources


def _put_path(root: dict, path: str, value: Any) -> None:
    parts = re.findall(r"([^.[\]]+)|\[(\d+)\]", path)
    keys = [int(index) if index else name for name, index in parts]
    target: Any = root
    for offset, key in enumerate(keys):
        if isinstance(target, list):
            while len(target) <= key:
                target.append(None)
        if offset == len(keys) - 1:
            target[key] = value
        else:
            child = [] if isinstance(keys[offset + 1], int) else {}
            if isinstance(target, list):
                if target[key] is None:
                    target[key] = child
            else:
                target.setdefault(key, child)
            target = target[key]


def read_items_csv(path: Path) -> tuple[list[RawIntelItem], int]:
    """Read both Mongo Compass flattened exports and our lossless CSV export."""
    csv.field_size_limit(100_000_000)
    items: dict[str, RawIntelItem] = {}
    rows = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row_number, row in enumerate(reader, start=2):
            doc: dict[str, Any] = {}
            try:
                if None in row:
                    raise ValueError("CSV row has extra columns")
                for key, value in row.items():
                    if value is None or value == "":
                        continue
                    parsed: Any = value
                    if key in {"metadata", "topics", "run_ids"}:
                        parsed = json.loads(value)
                    elif key == "relevance_score" or key.startswith(("metadata.topic_scores.", "metadata.relevance.score")):
                        parsed = float(value)
                    elif key.startswith("metadata.source_query_params."):
                        try:
                            parsed = json.loads(value)
                        except ValueError:
                            pass
                    _put_path(doc, key, parsed)
                doc["item_id"] = doc.get("item_id") or doc.get("_id")
                doc.pop("_id", None)
                metadata = doc.setdefault("metadata", {})
                metadata.setdefault("topics", doc.get("topics", []))
                if not doc.get("fetched_at"):
                    doc["fetched_at"] = (doc.get("last_seen_at") or doc.get("first_seen_at")
                                         or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
                item = RawIntelItem.model_validate(doc)
                if not item.item_id.strip():
                    raise ValueError("empty item_id")
                if item.item_id in items:
                    item = RawIntelItem.model_validate(merge_item_documents(
                        item.model_dump(mode="json"), items[item.item_id].model_dump(mode="json")
                    ))
                items[item.item_id] = item
                rows += 1
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"Invalid CSV row {row_number}: {exc}") from exc
    if not rows:
        raise ValueError("CSV contains no intelligence items")
    return list(items.values()), rows


def backup_store(store, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    if isinstance(store, JsonIntelRunStore):
        if store.root_dir.exists():
            shutil.copytree(store.root_dir, folder / "intel_runs", dirs_exist_ok=True)
    else:
        from bson.json_util import dumps
        for name, collection in (("items", store._items), ("runs", store._runs)):
            with (folder / f"{name}.jsonl").open("w", encoding="utf-8") as stream:
                for doc in collection.find({}):
                    stream.write(dumps(doc, ensure_ascii=False) + "\n")


def operation_folder(root: Path = Path("data/intel_agent/maintenance")) -> Path:
    return root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])


def import_csv(store, path: Path, *, dry_run: bool = False, output_dir: Path | None = None) -> dict:
    items, row_count = read_items_csv(path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    run_id = f"import_csv_{checksum[:16]}"
    existing = {doc["item_id"]: doc for doc in store.query_items(limit=100_000)}
    new_count = sum(item.item_id not in existing for item in items)
    merged = []
    for item in items:
        new = item.model_dump(mode="json")
        old = existing.get(item.item_id)
        if old:
            # The file is historical: newer local metadata remains authoritative.
            if str(old.get("fetched_at") or "") >= str(new.get("fetched_at") or ""):
                new = merge_item_documents(old, new)
            else:
                new = merge_item_documents(new, old)
        merged.append(RawIntelItem.model_validate(new))
    report = {"operation": "import_csv", "file": str(path.resolve()), "sha256": checksum,
              "run_id": run_id, "csv_rows": row_count, "unique_items": len(items),
              "new_items": new_count, "existing_items": len(items) - new_count,
              "total_items": len(existing) + new_count, "dry_run": dry_run}
    if not dry_run:
        output_dir = output_dir or operation_folder()
        backup_store(store, output_dir / "backup")
        board = IntelRunBlackboard(run_id=run_id, run_goal=f"历史情报 CSV 导入：{path.name}",
                                   run_mode="bootstrap", raw_items=merged,
                                   stop_reason="csv_import", import_report=report)
        store.save_run(board, status="succeeded")
        report["output_dir"] = str(output_dir.resolve())
        (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def fetch_original(item: RawIntelItem) -> tuple[str, str]:
    """Fetch by trusted source/id, never use an arbitrary imported URL."""
    identifier = item.item_id.split(":", 1)[-1]
    if item.source_name == "arxiv_api":
        if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", identifier, re.I):
            raise ValueError("Invalid arXiv identifier")
        url = sources.ARXIV_API_URL + "?" + urlencode({"id_list": identifier})
        matches = sources.parse_arxiv_items(sources._fetch_text(url, 25))
    elif item.source_name == "nvd_cve_api":
        url = sources.NVD_CVE_API_URL + "?" + urlencode({"cveId": identifier.upper()})
        matches = sources.parse_nvd_items(sources._fetch_json(url, 25))
    elif item.source_name == "osv_dev_api":
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", identifier):
            raise ValueError("Invalid OSV identifier")
        # GHSA's prefix is uppercase; its hash groups are lowercase.
        identifier = "GHSA-" + identifier[5:].lower() if identifier.lower().startswith("ghsa-") else identifier.upper()
        url = sources.OSV_VULN_URL + "/" + identifier
        matches = sources.parse_osv_vulnerability(sources._fetch_json(url, 25))
    elif item.source_name == "cisa_kev_json":
        url = sources.CISA_KEV_JSON_URL
        matches = sources.parse_cisa_kev_items(sources._fetch_json(url, 25), "", [identifier], None, 1)
    else:
        raise ValueError(f"Unsupported source: {item.source_name}")
    match = next((row for row in matches if row.item_id == item.item_id), None)
    if match is None or not match.raw_text:
        raise ValueError("Source did not return a matching nonempty record")
    return match.raw_text, url


def backfill_raw_text(store, *, dry_run: bool = False, output_dir: Path | None = None,
                      fetcher=fetch_original) -> dict:
    docs = store.query_items(limit=100_000)
    patches: dict[str, dict] = {}
    outcomes = []
    checked_at = datetime.now(timezone.utc).isoformat()
    originals: dict[str, tuple[str, str] | Exception] = {}
    if isinstance(store, JsonIntelRunStore):
        canonical = {doc["item_id"]: doc for doc in docs}
        for path in store.list_run_paths(limit=100_000):
            payload = store._read_payload(path)
            occurrences = list((payload.get("blackboard") or {}).get("raw_items") or [])
            for batch in payload.get("raw_item_batches") or []:
                occurrences.extend(batch.get("items") or [])
            for row in occurrences:
                best = canonical.get(row.get("item_id"), {})
                for field in ("raw_text", "summary"):
                    value = best.get(field)
                    if value and row.get(field) != value and preserve_text(row.get(field), value) == value:
                        patches.setdefault(row["item_id"], {})[field] = value

    def needs_check(raw: str) -> bool:
        return (not raw.strip() or raw.rstrip().endswith(("...", "…"))
                or ("\\n" in raw and "\n" not in raw))

    groups: dict[str, list[RawIntelItem]] = {}
    for doc in docs:
        raw = doc.get("raw_text") or ""
        if doc["source_name"] in {"arxiv_api", "nvd_cve_api"}:
            raw = preserve_text(raw, doc.get("summary")) or ""
        if needs_check(raw):
            groups.setdefault(doc["source_name"], []).append(RawIntelItem.model_validate(doc))

    def fetch_group(items: list[RawIntelItem]) -> dict:
        result = {}
        previous = 0.0
        for item in items:
            if fetcher is fetch_original:
                interval = {"nvd_cve_api": 0.7 if sources._setting("NVD_API_KEY") else 6.1,
                            "arxiv_api": 3.1}.get(item.source_name, 0.1)
                time.sleep(max(0, interval - (time.monotonic() - previous)))
            previous = time.monotonic()
            try:
                result[item.item_id] = fetcher(item)
            except Exception as exc:
                result[item.item_id] = exc
        return result

    if not dry_run:
        # Sources run independently; requests to each source remain sequential.
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(fetch_group, groups.values()):
                originals.update(result)
    for doc in docs:
        raw = doc.get("raw_text") or ""
        summary = doc.get("summary") or ""
        repaired = raw
        # Papers and NVD define raw text as their source summary/description.
        if doc["source_name"] in {"arxiv_api", "nvd_cve_api"}:
            repaired = preserve_text(raw, summary) or ""
        suspicious = needs_check(repaired)
        outcome: dict[str, Any] = {"item_id": doc["item_id"]}
        if suspicious and not dry_run:
            try:
                fetched = originals[doc["item_id"]]
                if isinstance(fetched, Exception):
                    raise fetched
                original, url = fetched
                repaired = preserve_text(original, repaired) or repaired
                outcome.update(status="source_ends_with_ellipsis" if original.rstrip().endswith(("...", "…"))
                               else "source_verified", source_url=url)
                if "\n" in original and raw == original.replace("\n", "\\n"):
                    outcome["status"] = "source_newlines_restored"
            except Exception as exc:
                outcome.update(status="fetch_failed", error=f"{type(exc).__name__}: {exc}")
        elif suspicious:
            outcome["status"] = "needs_source_check"
        elif repaired != raw:
            outcome["status"] = "recovered_from_summary"
        elif doc["item_id"] in patches:
            outcome["status"] = "recovered_from_history"
        else:
            continue
        patch: dict[str, Any] = patches.get(doc["item_id"], {})
        if repaired != raw:
            patch["raw_text"] = repaired
            outcome.update(old_chars=len(raw), new_chars=len(repaired))
        if doc["source_name"] in {"arxiv_api", "nvd_cve_api"}:
            full_summary = preserve_text(summary, repaired)
            if full_summary != summary:
                patch["summary"] = full_summary
        if not dry_run:
            patch["metadata"] = {"raw_text_check": {**outcome, "checked_at": checked_at}}
        if patch:
            patches[doc["item_id"]] = patch
        outcomes.append(outcome)
    report = {"operation": "backfill_raw_text", "checked_items": len(docs), "dry_run": dry_run,
              "text_updates": sum("raw_text" in patch or "summary" in patch for patch in patches.values()),
              "source_checks": len(outcomes), "results": outcomes,
              "missing_before": sum(not (doc.get("raw_text") or "").strip() for doc in docs)}
    if not dry_run:
        output_dir = output_dir or operation_folder()
        backup_store(store, output_dir / "backup")
        report["updated_items"] = store.update_item_texts(patches)
        report["missing_after"] = sum(not (doc.get("raw_text") or "").strip() for doc in store.query_items(limit=100_000))
        report["output_dir"] = str(output_dir.resolve())
        (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
