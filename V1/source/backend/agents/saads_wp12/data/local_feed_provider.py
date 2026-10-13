from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.agents.saads_wp12.data.models import AttackTaxonomyItem, Wp12AttackFeedItem


class LocalAttackFeedProvider:
    """Read exported WP1-2 feed items from local JSON resources."""

    def __init__(
        self,
        *,
        root_path: str,
        min_cvss: float = 0.0,
        limit: int = 500,
        taxonomy_codes: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._root_path = Path(root_path)
        self._min_cvss = min_cvss
        self._limit = limit
        self._taxonomy_codes = tuple(
            code.strip().upper()
            for code in (taxonomy_codes or [])
            if str(code).strip()
        )
        self._index_path = self._root_path / "manifests" / "attack_index.json"
        self._items_dir = self._root_path / "items"

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_path.exists():
            raise FileNotFoundError(
                f"Local feed index does not exist: {self._index_path}"
            )
        payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError(f"Invalid local feed index format: {self._index_path}")
        return [row for row in items if isinstance(row, dict)]

    @staticmethod
    def _taxonomy_codes_from_payload(payload: dict[str, Any]) -> set[str]:
        codes: set[str] = set()
        primary_code = str(payload.get("taxonomy_code", "") or "").strip().upper()
        if primary_code:
            codes.add(primary_code)
        for taxonomy in payload.get("all_taxonomies", []):
            if not isinstance(taxonomy, dict):
                continue
            taxonomy_code = str(taxonomy.get("taxonomy_code", "") or "").strip().upper()
            if taxonomy_code:
                codes.add(taxonomy_code)
        return codes

    def _matches_taxonomy_filter(self, payload: dict[str, Any]) -> bool:
        if not self._taxonomy_codes:
            return True
        return bool(self._taxonomy_codes_from_payload(payload).intersection(self._taxonomy_codes))

    def _matches_min_cvss(self, payload: dict[str, Any]) -> bool:
        score = payload.get("primary_cvss_base_score", 0.0)
        try:
            numeric_score = float(score or 0.0)
        except (TypeError, ValueError):
            numeric_score = 0.0
        return numeric_score >= self._min_cvss

    def _load_payload_by_attack_id(self, attack_id: str) -> dict[str, Any]:
        item_path = self._items_dir / f"{attack_id}.json"
        if not item_path.exists():
            raise KeyError(f"Unknown local attack_id: {attack_id}")
        payload = json.loads(item_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid local feed item format: {item_path}")
        return payload

    @staticmethod
    def _normalize_attack_identifier(
        attack_ref: str | tuple[str, str] | None,
    ) -> str | None:
        if attack_ref is None:
            return None
        if isinstance(attack_ref, tuple):
            if not attack_ref:
                return None
            return str(attack_ref[0]).strip()
        return str(attack_ref).strip()

    @staticmethod
    def _map_taxonomy_item(payload: dict[str, Any]) -> AttackTaxonomyItem:
        return AttackTaxonomyItem(
            map_id=int(payload.get("map_id", 0) or 0),
            taxonomy_type=str(payload.get("taxonomy_type", "") or ""),
            taxonomy_code=str(payload.get("taxonomy_code", "") or ""),
            taxonomy_name=str(payload.get("taxonomy_name", "") or ""),
            is_primary=bool(payload.get("is_primary", False)),
            confidence_score=float(payload.get("confidence_score", 0.0) or 0.0),
        )

    @classmethod
    def _map_payload_to_item(cls, payload: dict[str, Any]) -> Wp12AttackFeedItem:
        taxonomy_items = [
            cls._map_taxonomy_item(entry)
            for entry in payload.get("all_taxonomies", [])
            if isinstance(entry, dict)
        ]
        return Wp12AttackFeedItem(
            attack_id=str(payload.get("attack_id", "") or ""),
            attack_code=str(payload.get("attack_code", "") or ""),
            canonical_name=str(payload.get("canonical_name", "") or ""),
            attack_family=str(payload.get("attack_family", "") or ""),
            severity_level=str(payload.get("severity_level", "") or ""),
            entry_status=str(payload.get("entry_status", "") or ""),
            summary=str(payload.get("summary", "") or ""),
            last_seen_at=str(payload.get("last_seen_at", "") or ""),
            primary_cvss_version=str(payload.get("primary_cvss_version", "") or ""),
            primary_cvss_base_score=float(payload.get("primary_cvss_base_score", 0.0) or 0.0),
            primary_cvss_vector=str(payload.get("primary_cvss_vector", "") or ""),
            primary_cvss_severity_label=str(payload.get("primary_cvss_severity_label", "") or ""),
            taxonomy_type=str(payload.get("taxonomy_type", "") or ""),
            taxonomy_code=str(payload.get("taxonomy_code", "") or ""),
            taxonomy_name=str(payload.get("taxonomy_name", "") or ""),
            component_id=str(payload.get("component_id", "") or ""),
            component_name=str(payload.get("component_name", "") or ""),
            version_constraint_raw=str(payload.get("version_constraint_raw", "") or ""),
            normalized_constraint=str(payload.get("normalized_constraint", "") or ""),
            component_impact_scope=str(payload.get("component_impact_scope", "") or ""),
            asset_id=str(payload.get("asset_id", "") or ""),
            asset_type=str(payload.get("asset_type", "") or ""),
            asset_name=str(payload.get("asset_name", "") or ""),
            artifact_uri=str(payload.get("artifact_uri", "") or ""),
            qa_status=str(payload.get("qa_status", "") or ""),
            active=bool(payload.get("active", False)),
            all_taxonomies=taxonomy_items,
            description=str(payload.get("description", "") or ""),
            exploit_preconditions=str(payload.get("exploit_preconditions", "") or ""),
            attack_impact_scope=str(payload.get("attack_impact_scope", "") or ""),
            attack_confidence_score=float(payload.get("attack_confidence_score", 0.0) or 0.0),
            stix_type=str(payload.get("stix_type", "") or ""),
            stix_payload=payload.get("stix_payload") or {},
            component_context=payload.get("component_context") or {},
            published_seed_assets=payload.get("published_seed_assets") or [],
            component_risk_overview=payload.get("component_risk_overview") or {},
        )

    def _iter_filtered_payloads(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for row in self._load_index():
            attack_id = str(row.get("attack_id", "") or "").strip()
            if not attack_id:
                continue
            payload = self._load_payload_by_attack_id(attack_id)
            if not self._matches_min_cvss(payload):
                continue
            if not self._matches_taxonomy_filter(payload):
                continue
            payloads.append(payload)
            if len(payloads) >= self._limit:
                break
        return payloads

    def list_attack_feed_refs(self) -> list[tuple[str, str]]:
        refs: list[tuple[str, str]] = []
        for payload in self._iter_filtered_payloads():
            refs.append(
                (
                    str(payload.get("attack_id", "") or ""),
                    str(payload.get("attack_code", "") or ""),
                )
            )
        return refs

    def list_attack_feed_snapshots(self) -> list[Wp12AttackFeedItem]:
        return [self._map_payload_to_item(payload) for payload in self._iter_filtered_payloads()]

    def list_attack_feed_items(self) -> list[Wp12AttackFeedItem]:
        return self.list_attack_feed_snapshots()

    def collect_attack_feed_items(
        self,
        attack_refs: list[tuple[str, str]],
        *,
        continue_on_error: bool = True,
    ) -> tuple[list[Wp12AttackFeedItem], list[dict[str, str]]]:
        items: list[Wp12AttackFeedItem] = []
        errors: list[dict[str, str]] = []
        for attack_id, attack_code in attack_refs:
            try:
                items.append(self.get_attack_feed_item(attack_id))
            except Exception as exc:
                errors.append(
                    {
                        "attack_id": attack_id,
                        "attack_code": attack_code,
                        "error": str(exc),
                    }
                )
                if not continue_on_error:
                    raise
        return items, errors

    def get_attack_feed_item(
        self,
        attack_id: str | tuple[str, str] | None = None,
    ) -> Wp12AttackFeedItem:
        attack_identifier = self._normalize_attack_identifier(attack_id)

        if attack_identifier is None:
            payloads = self._iter_filtered_payloads()
            if not payloads:
                raise LookupError("Local feed returned no rows for the configured filters.")
            return self._map_payload_to_item(payloads[0])

        payload = self._load_payload_by_attack_id(attack_identifier)
        if not self._matches_min_cvss(payload):
            raise KeyError(
                f"Attack identifier {attack_identifier} does not match configured CVSS threshold {self._min_cvss}."
            )
        if not self._matches_taxonomy_filter(payload):
            raise KeyError(
                f"Attack identifier {attack_identifier} does not match configured taxonomy filters {self._taxonomy_codes}."
            )
        return self._map_payload_to_item(payload)
