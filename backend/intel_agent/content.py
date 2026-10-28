"""Lossless text merging shared by collection and historical imports."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def preserve_text(incoming: str | None, existing: str | None) -> str | None:
    """Keep a complete value when a later sighting is empty or a clipped prefix.

    A genuinely revised (possibly shorter) description is still accepted.
    Whitespace is normalized only for comparison, never for storage.
    """
    if not incoming or not incoming.strip():
        return existing or incoming
    if not existing:
        return incoming
    # Compass CSV escapes newlines without escaping literal backslashes. Only
    # recover them when an independently stored source text matches exactly.
    if "\n" not in incoming and "\n" in existing and incoming == existing.replace("\n", "\\n"):
        return existing
    if "\n" in incoming and "\n" not in existing and existing == incoming.replace("\n", "\\n"):
        return incoming
    new, old = " ".join(incoming.split()), " ".join(existing.split())
    prefix = new.rstrip(". …")
    if len(old) > len(new) and prefix and old.startswith(prefix):
        return existing
    return incoming


def merge_item_documents(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    """Merge a preferred sighting with an older one, retaining full text/history."""
    result = {**deepcopy(old), **deepcopy(new)}
    result["metadata"] = {**old.get("metadata", {}), **new.get("metadata", {})}
    for key in ("raw_text", "summary"):
        result[key] = preserve_text(new.get(key), old.get(key))
    result["run_ids"] = list(dict.fromkeys([*new.get("run_ids", []), *old.get("run_ids", [])]))
    # Imported provenance must survive subsequent collection sightings.
    first = min((doc for doc in (old, new) if doc.get("first_seen_at")),
                key=lambda doc: str(doc["first_seen_at"]), default={})
    for key in ("first_seen_at", "first_run_id"):
        if first.get(key):
            result[key] = first[key]
    return result
