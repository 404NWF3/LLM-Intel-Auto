from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AttackTaxonomyItem:
    map_id: int
    taxonomy_type: str
    taxonomy_code: str
    taxonomy_name: str
    is_primary: bool
    confidence_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Wp12AttackFeedItem:
    attack_id: str
    attack_code: str
    canonical_name: str
    attack_family: str
    severity_level: str
    entry_status: str
    summary: str
    last_seen_at: str
    primary_cvss_version: str
    primary_cvss_base_score: float
    primary_cvss_vector: str
    primary_cvss_severity_label: str
    taxonomy_type: str
    taxonomy_code: str
    taxonomy_name: str
    component_id: str
    component_name: str
    version_constraint_raw: str
    normalized_constraint: str
    component_impact_scope: str
    asset_id: str
    asset_type: str
    asset_name: str
    artifact_uri: str
    qa_status: str
    active: bool
    all_taxonomies: list[AttackTaxonomyItem] = field(default_factory=list)
    description: str = ""
    exploit_preconditions: str = ""
    attack_impact_scope: str = ""
    attack_confidence_score: float = 0.0
    stix_type: str = ""
    stix_payload: dict[str, Any] | None = None
    component_context: dict[str, Any] = field(default_factory=dict)
    published_seed_assets: list[dict[str, Any]] = field(default_factory=list)
    component_risk_overview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
