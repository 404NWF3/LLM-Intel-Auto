from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agents.saads_wp12.agent import graph
from backend.agents.saads_wp12.config import get_config
from backend.agents.saads_wp12.data.feed_provider import get_attack_feed_provider


def _registry_path() -> Path:
    configured_path = os.getenv("WP12_DEDUP_REGISTRY_PATH", "").strip()
    if configured_path:
        return Path(configured_path)
    return Path("artifacts") / "processed_attack_ids.json"


def _process_limit() -> int | None:
    raw_limit = os.getenv("WP12_PROCESS_LIMIT", "").strip()
    if not raw_limit:
        return None
    limit = int(raw_limit)
    if limit <= 0:
        return None
    return limit


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "processed_attacks": {},
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid dedup registry format: {path}")
    processed_attacks = payload.get("processed_attacks")
    if not isinstance(processed_attacks, dict):
        payload["processed_attacks"] = {}
    return payload


def _save_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _build_initial_state(feed_item: Any, *, feed_source: str) -> dict[str, Any]:
    return {
        "attack_id": feed_item.attack_id,
        "intel_raw": feed_item.to_dict(),
        "tenant_id": "feed-once",
        "scenario_id": f"{feed_source}-feed-once",
    }


def run_feed_once() -> dict[str, Any]:
    config = get_config()
    provider = get_attack_feed_provider()
    registry_path = _registry_path()
    registry = _load_registry(registry_path)
    processed_attacks = registry.setdefault("processed_attacks", {})
    if not isinstance(processed_attacks, dict):
        raise ValueError(f"Invalid processed_attacks payload in registry: {registry_path}")

    attack_refs = provider.list_attack_feed_refs()
    unseen_refs = [
        attack_ref
        for attack_ref in attack_refs
        if attack_ref[0] not in processed_attacks
    ]
    process_limit = _process_limit()
    if process_limit is not None:
        unseen_refs = unseen_refs[:process_limit]

    if not unseen_refs:
        return {
            "status": "idle",
            "feed_source": config.feed_source,
            "feed_items_seen": len(attack_refs),
            "skipped_existing": len(attack_refs),
            "processed_count": 0,
            "registry_path": str(registry_path),
            "message": "No unseen attack identifiers were available.",
        }

    feed_items, feed_errors = provider.collect_attack_feed_items(
        unseen_refs,
        continue_on_error=True,
    )
    results: list[dict[str, Any]] = []
    runtime_errors: list[dict[str, str]] = list(feed_errors)

    for feed_item in feed_items:
        attack_id = feed_item.attack_id
        try:
            result = graph.invoke(_build_initial_state(feed_item, feed_source=config.feed_source))
        except Exception as exc:
            runtime_errors.append(
                {
                    "attack_id": attack_id,
                    "error": str(exc),
                }
            )
            continue

        processed_attacks[attack_id] = {
            "attack_code": feed_item.attack_code,
            "processed_at": datetime.now(UTC).isoformat(),
            "run_id": result.get("run_id", ""),
            "verdict": result.get("verdict", ""),
            "persistence_path": result.get("persistence_path", ""),
        }
        results.append(
            {
                "attack_id": attack_id,
                "attack_code": feed_item.attack_code,
                "run_id": result.get("run_id", ""),
                "verdict": result.get("verdict", ""),
                "persistence_path": result.get("persistence_path", ""),
            }
        )

    _save_registry(registry_path, registry)

    return {
        "status": "done" if results else "error",
        "feed_source": config.feed_source,
        "feed_items_seen": len(attack_refs),
        "skipped_existing": len(attack_refs) - len(unseen_refs),
        "requested_to_process": len(unseen_refs),
        "processed_count": len(results),
        "error_count": len(runtime_errors),
        "registry_path": str(registry_path),
        "results": results,
        "errors": runtime_errors,
    }


def main() -> None:
    print(json.dumps(run_feed_once(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
