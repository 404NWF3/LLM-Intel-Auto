from __future__ import annotations

import importlib
import os
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, TypeVar

from backend.agents.saads_wp12.data.models import AttackTaxonomyItem, Wp12AttackFeedItem

T = TypeVar("T")


class DbAttackFeedProvider:
    """Read WP1-2 feed rows from the main repository's db layer."""

    def __init__(
        self,
        *,
        main_backend_path: str,
        min_cvss: float = 0.0,
        limit: int = 500,
        taxonomy_codes: list[str] | tuple[str, ...] | None = None,
        backend_db_env: dict[str, str] | None = None,
    ) -> None:
        self._main_backend_path = Path(main_backend_path)
        self._min_cvss = min_cvss
        self._limit = limit
        self._taxonomy_codes = tuple(
            code.strip().upper()
            for code in (taxonomy_codes or [])
            if str(code).strip()
        )
        self._backend_db_env = {
            str(key): str(value)
            for key, value in (backend_db_env or {}).items()
            if str(key).strip() and str(value).strip()
        }

    def _apply_backend_db_env_overrides(self) -> None:
        for key, value in self._backend_db_env.items():
            os.environ[key] = value

    def _ensure_backend_import_path(self) -> None:
        if not self._main_backend_path.exists():
            raise FileNotFoundError(
                f"SAADS main backend path does not exist: {self._main_backend_path}"
            )
        backend_str = str(self._main_backend_path)
        if backend_str not in sys.path:
            sys.path.insert(0, backend_str)

    def _load_main_repo_modules(self) -> tuple[Any, Any, Any, Any]:
        self._ensure_backend_import_path()
        self._apply_backend_db_env_overrides()
        connection = importlib.import_module("db.connection")
        unit_of_work = importlib.import_module("db.unit_of_work")
        feed_service = importlib.import_module("db.services.wp12_feed_service")
        return (
            connection.init_pool,
            connection.close_pool,
            unit_of_work.UnitOfWork,
            feed_service.Wp12FeedService,
        )

    @staticmethod
    def _decimal_to_float(value: Decimal | None) -> float:
        return float(value) if value is not None else 0.0

    @staticmethod
    def _datetime_to_iso(value: datetime | None) -> str:
        return value.isoformat() if value is not None else ""

    @staticmethod
    def _row_matches_attack(row: Any, attack_id: str) -> bool:
        attack_id_normalized = attack_id.strip()
        return str(row.attack_id) == attack_id_normalized or row.attack_code == attack_id_normalized

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
    def _extract_taxonomy_codes(
        row: Any,
        taxonomy_maps: list[Any] | None = None,
    ) -> set[str]:
        codes: set[str] = set()
        row_taxonomy_code = str(getattr(row, "taxonomy_code", "") or "").strip().upper()
        if row_taxonomy_code:
            codes.add(row_taxonomy_code)
        for taxonomy_map in taxonomy_maps or []:
            taxonomy_code = str(getattr(taxonomy_map, "taxonomy_code", "") or "").strip().upper()
            if taxonomy_code:
                codes.add(taxonomy_code)
        return codes

    def _matches_taxonomy_filter(
        self,
        row: Any,
        taxonomy_maps: list[Any] | None = None,
    ) -> bool:
        if not self._taxonomy_codes:
            return True
        return bool(self._extract_taxonomy_codes(row, taxonomy_maps).intersection(self._taxonomy_codes))

    @staticmethod
    def _map_taxonomy_map(taxonomy_map: Any) -> AttackTaxonomyItem:
        return AttackTaxonomyItem(
            map_id=int(taxonomy_map.map_id),
            taxonomy_type=taxonomy_map.taxonomy_type or "",
            taxonomy_code=taxonomy_map.taxonomy_code or "",
            taxonomy_name=taxonomy_map.taxonomy_name or "",
            is_primary=bool(taxonomy_map.is_primary),
            confidence_score=DbAttackFeedProvider._decimal_to_float(
                getattr(taxonomy_map, "confidence_score", None)
            ),
        )

    @classmethod
    def _map_seed_asset(cls, seed_asset: Any) -> dict[str, Any]:
        return {
            "asset_id": str(seed_asset.asset_id),
            "asset_type": seed_asset.asset_type or "",
            "asset_name": seed_asset.asset_name or "",
            "artifact_uri": seed_asset.artifact_uri or "",
            "checksum": seed_asset.checksum or "",
            "language": seed_asset.language or "",
            "modality": seed_asset.modality or "",
            "qa_status": seed_asset.qa_status or "",
            "is_template": bool(seed_asset.is_template),
            "metadata_json": seed_asset.metadata_json or {},
            "created_at": cls._datetime_to_iso(seed_asset.created_at),
        }

    @classmethod
    def _map_component_detail(
        cls,
        component: Any | None,
        component_aliases: list[Any],
        component_impacts: list[Any],
    ) -> dict[str, Any]:
        return {
            "component_id": str(component.component_id) if component is not None else "",
            "component_code": component.component_code if component is not None else "",
            "component_name": component.component_name if component is not None else "",
            "component_layer": component.component_layer if component is not None else "",
            "vendor_name": component.vendor_name if component is not None else "",
            "component_type": component.component_type if component is not None else "",
            "modality": component.modality if component is not None else "",
            "purl": component.purl if component is not None else "",
            "homepage_uri": component.homepage_uri if component is not None else "",
            "lifecycle_status": component.lifecycle_status if component is not None else "",
            "aliases": [
                {
                    "alias_id": int(alias.alias_id),
                    "alias_name": alias.alias_name,
                    "alias_type": alias.alias_type,
                    "normalized_alias": alias.normalized_alias,
                    "is_preferred": bool(alias.is_preferred),
                }
                for alias in component_aliases
            ],
            "impacts": [
                {
                    "impact_id": str(impact.impact_id),
                    "component_id": str(impact.component_id),
                    "version_constraint_raw": impact.version_constraint_raw or "",
                    "normalized_constraint": impact.normalized_constraint or "",
                    "match_mode": impact.match_mode or "",
                    "impact_scope": impact.impact_scope or "",
                    "confidence_score": cls._decimal_to_float(impact.confidence_score),
                    "evidence_uri": impact.evidence_uri or "",
                    "created_at": cls._datetime_to_iso(impact.created_at),
                }
                for impact in component_impacts
            ],
        }

    @classmethod
    def _map_component_risk_overview(cls, row: Any | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "component_id": str(row.component_id),
            "component_code": row.component_code,
            "component_name": row.component_name,
            "vendor_name": row.vendor_name or "",
            "component_type": row.component_type,
            "attack_count": int(row.attack_count),
            "high_cvss_attack_count": int(row.high_cvss_attack_count),
            "critical_cvss_attack_count": int(row.critical_cvss_attack_count),
            "latest_seen_at": cls._datetime_to_iso(row.latest_seen_at),
            "max_primary_cvss_score": cls._decimal_to_float(row.max_primary_cvss_score),
            "avg_primary_cvss_score": cls._decimal_to_float(row.avg_primary_cvss_score),
        }

    @classmethod
    def _map_attack_entry(cls, attack_entry: Any | None) -> dict[str, Any]:
        if attack_entry is None:
            return {}
        return {
            "description": attack_entry.description or "",
            "exploit_preconditions": attack_entry.exploit_preconditions or "",
            "impact_scope": attack_entry.impact_scope or "",
            "confidence_score": cls._decimal_to_float(attack_entry.confidence_score),
            "stix_type": attack_entry.stix_type or "",
            "stix_payload": attack_entry.stix_payload or {},
        }

    def _run_feed_query_with_retry(self, query_fn: Callable[[Any, Any, Any], T]) -> T:
        init_pool, close_pool, UnitOfWork, Wp12FeedService = self._load_main_repo_modules()
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                init_pool()
                return query_fn(UnitOfWork, Wp12FeedService, attempt)
            except Exception as exc:
                last_error = exc
                close_pool()
                if attempt == 2:
                    raise
                time.sleep(1.0 + attempt)

        assert last_error is not None
        raise last_error

    def _list_filtered_feed_rows(
        self,
        uow: Any,
        *,
        limit: int,
        offset: int = 0,
        active_only: bool = False,
        qa_statuses: list[str] | None = None,
    ) -> list[Any]:
        qa_statuses = qa_statuses or []
        query = """
SELECT
    feed.attack_id,
    feed.attack_code,
    feed.canonical_name,
    feed.attack_family,
    feed.severity_level,
    feed.entry_status,
    feed.summary,
    feed.last_seen_at,
    feed.primary_cvss_version,
    feed.primary_cvss_base_score,
    feed.primary_cvss_vector,
    feed.primary_cvss_severity_label,
    feed.taxonomy_type,
    feed.taxonomy_code,
    feed.taxonomy_name,
    feed.component_id,
    feed.component_name,
    feed.version_constraint_raw,
    feed.normalized_constraint,
    feed.component_impact_scope,
    feed.asset_id,
    feed.asset_type,
    feed.asset_name,
    feed.artifact_uri,
    feed.qa_status
FROM wp11.v_wp12_attack_feed AS feed
WHERE 1 = 1
"""
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if self._min_cvss is not None:
            query += " AND (feed.primary_cvss_base_score IS NULL OR feed.primary_cvss_base_score >= %(min_cvss)s)"
            params["min_cvss"] = self._min_cvss
        if active_only:
            query += " AND feed.entry_status = 'active'"
        if qa_statuses:
            query += " AND (feed.qa_status = ANY(%(qa_statuses)s) OR feed.qa_status IS NULL)"
            params["qa_statuses"] = qa_statuses
        if self._taxonomy_codes:
            query += """
 AND EXISTS (
    SELECT 1
    FROM wp11.attack_taxonomy_map AS atm
    WHERE atm.attack_id = feed.attack_id
      AND UPPER(atm.taxonomy_code) = ANY(%(taxonomy_codes)s)
 )
"""
            params["taxonomy_codes"] = list(self._taxonomy_codes)
        query += """
 ORDER BY feed.primary_cvss_base_score DESC NULLS LAST, feed.last_seen_at DESC NULLS LAST
 LIMIT %(limit)s OFFSET %(offset)s
"""
        rows = uow.read_models._fetch_all(query, params)
        return [SimpleNamespace(**row) for row in rows]

    def _get_feed_row_by_attack_identifier(self, uow: Any, attack_id: str) -> Any | None:
        attack_id_normalized = attack_id.strip()
        query = """
SELECT
    feed.attack_id,
    feed.attack_code,
    feed.canonical_name,
    feed.attack_family,
    feed.severity_level,
    feed.entry_status,
    feed.summary,
    feed.last_seen_at,
    feed.primary_cvss_version,
    feed.primary_cvss_base_score,
    feed.primary_cvss_vector,
    feed.primary_cvss_severity_label,
    feed.taxonomy_type,
    feed.taxonomy_code,
    feed.taxonomy_name,
    feed.component_id,
    feed.component_name,
    feed.version_constraint_raw,
    feed.normalized_constraint,
    feed.component_impact_scope,
    feed.asset_id,
    feed.asset_type,
    feed.asset_name,
    feed.artifact_uri,
    feed.qa_status
FROM wp11.v_wp12_attack_feed AS feed
WHERE
    (CAST(feed.attack_id AS TEXT) = %(attack_id)s OR feed.attack_code = %(attack_id)s)
"""
        params: dict[str, Any] = {"attack_id": attack_id_normalized}
        if self._min_cvss is not None:
            query += " AND (feed.primary_cvss_base_score IS NULL OR feed.primary_cvss_base_score >= %(min_cvss)s)"
            params["min_cvss"] = self._min_cvss
        if self._taxonomy_codes:
            query += """
 AND EXISTS (
    SELECT 1
    FROM wp11.attack_taxonomy_map AS atm
    WHERE atm.attack_id = feed.attack_id
      AND UPPER(atm.taxonomy_code) = ANY(%(taxonomy_codes)s)
 )
"""
            params["taxonomy_codes"] = list(self._taxonomy_codes)
        query += """
 ORDER BY feed.primary_cvss_base_score DESC NULLS LAST, feed.last_seen_at DESC NULLS LAST
 LIMIT 1
"""
        rows = uow.read_models._fetch_all(query, params)
        if not rows:
            return None
        return SimpleNamespace(**rows[0])

    def list_attack_feed_refs(self) -> list[tuple[str, str]]:
        """Return lightweight attack identifiers for batch processing.

        This keeps the first pass cheap when callers only need
        `(attack_id, attack_code)` before loading full feed items.
        """

        def _query(UnitOfWork: Any, Wp12FeedService: Any, _attempt: int) -> list[tuple[str, str]]:
            with UnitOfWork(read_only=True) as uow:
                if self._taxonomy_codes:
                    rows = self._list_filtered_feed_rows(
                        uow,
                        limit=self._limit,
                        active_only=False,
                        qa_statuses=[],
                    )
                else:
                    service = Wp12FeedService(uow)
                    rows = service.get_attack_feed(
                        min_cvss=self._min_cvss,
                        active_only=False,
                        qa_statuses=None,
                        limit=self._limit,
                    )
                feed_refs: list[tuple[str, str]] = []
                for row in rows:
                    if not self._taxonomy_codes or self._matches_taxonomy_filter(row):
                        feed_refs.append((str(row.attack_id), row.attack_code or ""))
                return feed_refs

        return self._run_feed_query_with_retry(_query)

    def list_attack_feed_snapshots(self) -> list[Wp12AttackFeedItem]:
        """Return feed items without the per-row taxonomy expansion."""

        def _query(UnitOfWork: Any, Wp12FeedService: Any, _attempt: int) -> list[Wp12AttackFeedItem]:
            with UnitOfWork(read_only=True) as uow:
                if self._taxonomy_codes:
                    rows = self._list_filtered_feed_rows(
                        uow,
                        limit=self._limit,
                        active_only=False,
                        qa_statuses=[],
                    )
                else:
                    service = Wp12FeedService(uow)
                    rows = service.get_attack_feed(
                        min_cvss=self._min_cvss,
                        active_only=False,
                        qa_statuses=None,
                        limit=self._limit,
                    )
                items: list[Wp12AttackFeedItem] = []
                for row in rows:
                    taxonomy_maps = None
                    if self._taxonomy_codes:
                        taxonomy_maps = uow.attacks.list_taxonomy_maps(str(row.attack_id))
                    if not self._taxonomy_codes or self._matches_taxonomy_filter(row, taxonomy_maps):
                        items.append(self._map_row_to_item(row, taxonomy_maps))
                return items

        return self._run_feed_query_with_retry(_query)

    def list_attack_feed_items(self) -> list[Wp12AttackFeedItem]:
        def _query(UnitOfWork: Any, Wp12FeedService: Any, _attempt: int) -> list[Wp12AttackFeedItem]:
            with UnitOfWork(read_only=True) as uow:
                if self._taxonomy_codes:
                    rows = self._list_filtered_feed_rows(
                        uow,
                        limit=self._limit,
                        active_only=False,
                        qa_statuses=[],
                    )
                else:
                    service = Wp12FeedService(uow)
                    rows = service.get_attack_feed(
                        min_cvss=self._min_cvss,
                        active_only=False,
                        qa_statuses=None,
                        limit=self._limit,
                    )
                items: list[Wp12AttackFeedItem] = []
                for row in rows:
                    taxonomy_maps = uow.attacks.list_taxonomy_maps(str(row.attack_id))
                    if not self._taxonomy_codes or self._matches_taxonomy_filter(row, taxonomy_maps):
                        items.append(self._map_row_to_item(row, taxonomy_maps))
                return items

        return self._run_feed_query_with_retry(_query)

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

    @classmethod
    def _map_row_to_item(
        cls,
        row: Any,
        taxonomy_maps: list[Any] | None = None,
        attack_entry: Any | None = None,
        component_context: dict[str, Any] | None = None,
        published_seed_assets: list[dict[str, Any]] | None = None,
        component_risk_overview: dict[str, Any] | None = None,
    ) -> Wp12AttackFeedItem:
        attack_entry_context = cls._map_attack_entry(attack_entry)
        return Wp12AttackFeedItem(
            attack_id=str(row.attack_id),
            attack_code=row.attack_code,
            canonical_name=row.canonical_name,
            attack_family=row.attack_family or "",
            severity_level=row.severity_level or "",
            entry_status=row.entry_status or "",
            summary=row.summary,
            last_seen_at=cls._datetime_to_iso(row.last_seen_at),
            primary_cvss_version=row.primary_cvss_version or "",
            primary_cvss_base_score=cls._decimal_to_float(row.primary_cvss_base_score),
            primary_cvss_vector=row.primary_cvss_vector or "",
            primary_cvss_severity_label=row.primary_cvss_severity_label or "",
            taxonomy_type=row.taxonomy_type or "",
            taxonomy_code=row.taxonomy_code or "",
            taxonomy_name=row.taxonomy_name or "",
            component_id=str(row.component_id) if row.component_id is not None else "",
            component_name=row.component_name or "",
            version_constraint_raw=row.version_constraint_raw or "",
            normalized_constraint=row.normalized_constraint or "",
            component_impact_scope=row.component_impact_scope or "",
            asset_id=str(row.asset_id) if row.asset_id is not None else "",
            asset_type=row.asset_type or "",
            asset_name=row.asset_name or "",
            artifact_uri=row.artifact_uri or "",
            qa_status=row.qa_status or "",
            active=row.entry_status == "active",
            all_taxonomies=[
                cls._map_taxonomy_map(taxonomy_map) for taxonomy_map in (taxonomy_maps or [])
            ],
            description=attack_entry_context.get("description", ""),
            exploit_preconditions=attack_entry_context.get("exploit_preconditions", ""),
            attack_impact_scope=attack_entry_context.get("impact_scope", ""),
            attack_confidence_score=attack_entry_context.get("confidence_score", 0.0),
            stix_type=attack_entry_context.get("stix_type", ""),
            stix_payload=attack_entry_context.get("stix_payload", {}),
            component_context=component_context or {},
            published_seed_assets=published_seed_assets or [],
            component_risk_overview=component_risk_overview or {},
        )

    def get_attack_feed_item(
        self,
        attack_id: str | tuple[str, str] | None = None,
    ) -> Wp12AttackFeedItem:
        attack_identifier = self._normalize_attack_identifier(attack_id)

        def _query(UnitOfWork: Any, Wp12FeedService: Any, _attempt: int) -> Wp12AttackFeedItem:
            with UnitOfWork(read_only=True) as uow:
                service = Wp12FeedService(uow)
                page_limit = max(self._limit, 100)
                offset = 0
                first_row: Any | None = None
                selected_row: Any | None = None

                if attack_identifier is not None:
                    selected_row = self._get_feed_row_by_attack_identifier(uow, attack_identifier)
                    if selected_row is None:
                        raise KeyError(f"Unknown attack identifier in db feed: {attack_identifier}")
                else:
                    while True:
                        if self._taxonomy_codes:
                            rows = self._list_filtered_feed_rows(
                                uow,
                                limit=page_limit,
                                offset=offset,
                                active_only=False,
                                qa_statuses=[],
                            )
                        else:
                            rows = service.get_attack_feed(
                                min_cvss=self._min_cvss,
                                active_only=False,
                                qa_statuses=None,
                                limit=page_limit,
                                offset=offset,
                            )
                        if not rows:
                            break
                        if first_row is None:
                            first_row = rows[0]
                        if attack_identifier is None:
                            selected_row = rows[0]
                            break
                        for row in rows:
                            if self._row_matches_attack(row, attack_identifier):
                                taxonomy_maps = uow.attacks.list_taxonomy_maps(str(row.attack_id))
                                if self._matches_taxonomy_filter(row, taxonomy_maps):
                                    selected_row = row
                                    break
                        if selected_row is not None:
                            break
                        if attack_identifier is None and self._taxonomy_codes:
                            for row in rows:
                                taxonomy_maps = uow.attacks.list_taxonomy_maps(str(row.attack_id))
                                if self._matches_taxonomy_filter(row, taxonomy_maps):
                                    selected_row = row
                                    break
                            if selected_row is not None:
                                break
                        if len(rows) < page_limit:
                            break
                        offset += page_limit

                if selected_row is None and attack_identifier is None:
                    selected_row = first_row
                if selected_row is None:
                    if first_row is None:
                        raise LookupError("WP1-2 db feed returned no rows.")
                    raise KeyError(f"Unknown attack identifier in db feed: {attack_identifier}")

                attack_id_str = str(selected_row.attack_id)
                taxonomy_maps = uow.attacks.list_taxonomy_maps(attack_id_str)
                if not self._matches_taxonomy_filter(selected_row, taxonomy_maps):
                    if attack_identifier is None:
                        raise LookupError("WP1-2 db feed returned no rows for the configured taxonomy filters.")
                    raise KeyError(
                        f"Attack identifier {attack_identifier} does not match configured taxonomy filters {self._taxonomy_codes}."
                    )
                attack_entry = uow.attacks.get_attack_by_id(attack_id_str)
                component_impacts = uow.components.list_component_impacts_by_attack(attack_id_str)
                component_detail = None
                component_aliases: list[Any] = []
                if selected_row.component_name:
                    component_detail = uow.components.get_component_by_name(selected_row.component_name)
                    if component_detail is not None:
                        component_aliases = uow.components.list_component_aliases(
                            str(component_detail.component_id)
                        )
                published_seed_assets = [
                    self._map_seed_asset(asset)
                    for asset in uow.attacks.list_published_seed_assets(attack_id_str)
                ]
                component_risk_overview = {}
                if component_detail is not None:
                    risk_rows = uow.read_models.list_component_risk_overview(limit=500)
                    matched_risk = next(
                        (
                            risk_row
                            for risk_row in risk_rows
                            if str(risk_row.component_id) == str(component_detail.component_id)
                        ),
                        None,
                    )
                    component_risk_overview = self._map_component_risk_overview(matched_risk)

                return self._map_row_to_item(
                    selected_row,
                    taxonomy_maps,
                    attack_entry=attack_entry,
                    component_context=self._map_component_detail(
                        component_detail,
                        component_aliases,
                        component_impacts,
                    ),
                    published_seed_assets=published_seed_assets,
                    component_risk_overview=component_risk_overview,
                )

        return self._run_feed_query_with_retry(_query)
