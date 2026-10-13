from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4
from typing import Any

from backend.agents.saads_wp12.data.feed_provider import get_attack_feed_provider
from backend.agents.saads_wp12.state import SecurityEvalState

SUPPORTED_ATTACK_FAMILIES = {
    "prompt_injection",
    "long_horizon_dialogue",
    "tool_hijack",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalized_all_taxonomies(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = raw.get("all_taxonomies") or []
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        normalized_items.append(
            {
                "map_id": int(item.get("map_id", 0) or 0),
                "taxonomy_type": _clean_text(item.get("taxonomy_type")),
                "taxonomy_code": _clean_text(item.get("taxonomy_code")),
                "taxonomy_name": _clean_text(item.get("taxonomy_name")),
                "is_primary": bool(item.get("is_primary", False)),
                "confidence_score": _coerce_float(item.get("confidence_score")),
            }
        )
    return normalized_items


def _infer_attack_family(raw: dict[str, Any]) -> tuple[str, list[str]]:
    feed_attack_family = _clean_text(raw.get("attack_family")).lower()
    taxonomy_code = _clean_text(raw.get("taxonomy_code")).upper()
    taxonomy_name = _clean_text(raw.get("taxonomy_name")).lower()
    asset_type = _clean_text(raw.get("asset_type")).lower()
    summary = _clean_text(raw.get("summary")).lower()
    canonical_name = _clean_text(raw.get("canonical_name")).lower()
    text_blob = " ".join([taxonomy_name, summary, canonical_name]).strip()

    if feed_attack_family in SUPPORTED_ATTACK_FAMILIES:
        return feed_attack_family, [f"feed_attack_family:{feed_attack_family}"]

    family_from_taxonomy = {
        "LLM01": "prompt_injection",
        "OWASP-LLM-01": "prompt_injection",
        "LLM02": "tool_hijack",
        "OWASP-LLM-02": "tool_hijack",
    }
    family_from_asset_type = {
        "prompt_corpus": "long_horizon_dialogue",
        "payload_template": "prompt_injection",
        "rule": "tool_hijack",
    }
    if taxonomy_code in family_from_taxonomy:
        return family_from_taxonomy[taxonomy_code], [f"taxonomy_code:{taxonomy_code}"]

    all_taxonomies = _normalized_all_taxonomies(raw)
    for taxonomy in all_taxonomies:
        taxonomy_code_candidate = taxonomy["taxonomy_code"].upper()
        if taxonomy_code_candidate in family_from_taxonomy:
            return family_from_taxonomy[taxonomy_code_candidate], [
                f"all_taxonomy_code:{taxonomy_code_candidate}"
            ]

    if asset_type in family_from_asset_type:
        return family_from_asset_type[asset_type], [f"asset_type:{asset_type}"]

    signals: list[str] = []
    if any(keyword in text_blob for keyword in ["tool", "function call", "function-calling", "argument", "invocation"]):
        signals.append("text:tool_hijack")
    if any(keyword in text_blob for keyword in ["multi-turn", "dialogue", "conversation", "long horizon", "long-horizon"]):
        signals.append("text:long_horizon_dialogue")
    if any(keyword in text_blob for keyword in ["prompt injection", "retrieved instruction", "instruction hidden", "malicious instruction"]):
        signals.append("text:prompt_injection")

    if signals:
        preferred = {
            "text:tool_hijack": "tool_hijack",
            "text:long_horizon_dialogue": "long_horizon_dialogue",
            "text:prompt_injection": "prompt_injection",
        }
        return preferred[signals[0]], signals

    if taxonomy_code or all_taxonomies or taxonomy_name:
        taxonomy_signal = taxonomy_code or "non_llm_taxonomy_present"
        return "unknown", [f"fallback:unknown_non_llm_taxonomy:{taxonomy_signal}"]

    return "prompt_injection", ["fallback:prompt_injection"]


def _build_risk_flags(normalized: dict[str, Any]) -> list[str]:
    risk_flags: list[str] = []
    if normalized["primary_cvss_base_score"] >= 8.0:
        risk_flags.append("high_severity")
    if normalized["seed_asset"]["qa_status"] not in {"reviewed", "published"}:
        risk_flags.append("asset_not_ready")
    if not normalized["summary"]:
        risk_flags.append("missing_summary")
    if not normalized["taxonomy"]["code"]:
        risk_flags.append("missing_taxonomy_code")
    if not normalized["component"]["name"] and not normalized["component"]["version_constraint"]:
        risk_flags.append("missing_component_context")
    if not normalized["seed_asset"]["artifact_uri"]:
        risk_flags.append("missing_seed_artifact")
    if not normalized["seed_asset"]["asset_type"]:
        risk_flags.append("missing_seed_asset_type")
    return risk_flags


def _build_bom_component_context(raw: dict[str, Any]) -> dict[str, Any]:
    existing = raw.get("component_context")
    if existing:
        return existing
    component_id = _clean_text(raw.get("component_id"))
    component_name = _clean_text(raw.get("component_name"))
    version_constraint = _clean_text(raw.get("version_constraint_raw"))
    impact_scope = _clean_text(raw.get("component_impact_scope"))
    if not any([component_id, component_name, version_constraint, impact_scope]):
        return {}
    return {
        "component_id": component_id,
        "component_code": component_id,
        "component_name": component_name,
        "component_layer": impact_scope,
        "vendor_name": "",
        "component_type": component_name,
        "modality": "",
        "purl": "",
        "homepage_uri": "",
        "lifecycle_status": "",
        "aliases": [],
        "impacts": (
            [
                {
                    "impact_scope": impact_scope,
                    "version_constraint_raw": version_constraint,
                }
            ]
            if impact_scope or version_constraint
            else []
        ),
    }


def _build_published_seed_assets(raw: dict[str, Any]) -> list[dict[str, Any]]:
    existing = raw.get("published_seed_assets")
    if existing:
        return existing
    artifact_uri = _clean_text(raw.get("artifact_uri"))
    qa_status = _clean_text(raw.get("qa_status")).lower()
    if artifact_uri and qa_status in {"reviewed", "published"}:
        return [
            {
                "asset_id": _clean_text(raw.get("asset_id")),
                "asset_type": _clean_text(raw.get("asset_type")),
                "asset_name": _clean_text(raw.get("asset_name")),
                "artifact_uri": artifact_uri,
                "qa_status": qa_status,
            }
        ]
    return []


def ingest_intel(state: SecurityEvalState) -> dict:
    preloaded_intel = state.get("intel_raw")
    if preloaded_intel:
        feed_item_dict = dict(preloaded_intel)
    else:
        provider = get_attack_feed_provider()
        feed_item = provider.get_attack_feed_item(state.get("attack_id"))
        feed_item_dict = feed_item.to_dict()
    run_id = state.get("run_id", f"run-{uuid4().hex[:8]}")
    audit_log = list(state.get("audit_log", []))
    audit_log.append(
        {
            "event": "intel_ingested",
            "run_id": run_id,
            "attack_id": feed_item_dict.get("attack_id", state.get("attack_id", "")),
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    return {
        "run_id": run_id,
        "attack_id": feed_item_dict.get("attack_id", state.get("attack_id", "")),
        "intel_raw": feed_item_dict,
        "reflection_round": state.get("reflection_round", 0),
        "max_reflection_rounds": state.get("max_reflection_rounds", 1),
        "audit_log": audit_log,
    }


def normalize_intel(state: SecurityEvalState) -> dict:
    raw = state["intel_raw"]
    attack_family, family_inference_signals = _infer_attack_family(raw)
    normalized = {
        "attack_id": _clean_text(raw.get("attack_id")),
        "attack_code": _clean_text(raw.get("attack_code")),
        "canonical_name": _clean_text(raw.get("canonical_name")),
        "feed_attack_family": _clean_text(raw.get("attack_family")).lower(),
        "severity_level": _clean_text(raw.get("severity_level")),
        "entry_status": _clean_text(raw.get("entry_status")),
        "summary": _clean_text(raw.get("summary")),
        "attack_family": attack_family,
        "last_seen_at": _clean_text(raw.get("last_seen_at")),
        "attack_entry_context": {
            "description": _clean_text(raw.get("description")),
            "exploit_preconditions": _clean_text(raw.get("exploit_preconditions")),
            "impact_scope": _clean_text(raw.get("attack_impact_scope")),
            "confidence_score": _coerce_float(raw.get("attack_confidence_score")),
        },
        "stix_context": {
            "stix_type": _clean_text(raw.get("stix_type")),
            "stix_payload": raw.get("stix_payload") or {},
        },
        "primary_cvss_version": _clean_text(raw.get("primary_cvss_version")),
        "taxonomy": {
            "type": _clean_text(raw.get("taxonomy_type")),
            "code": _clean_text(raw.get("taxonomy_code")),
            "name": _clean_text(raw.get("taxonomy_name")),
        },
        "all_taxonomies": _normalized_all_taxonomies(raw),
        "component": {
            "id": _clean_text(raw.get("component_id")),
            "name": _clean_text(raw.get("component_name")),
            "version_constraint": _clean_text(raw.get("version_constraint_raw")),
            "normalized_constraint": _clean_text(raw.get("normalized_constraint")),
            "impact_scope": _clean_text(raw.get("component_impact_scope")),
        },
        "seed_asset": {
            "asset_id": _clean_text(raw.get("asset_id")),
            "asset_type": _clean_text(raw.get("asset_type")),
            "asset_name": _clean_text(raw.get("asset_name")),
            "artifact_uri": _clean_text(raw.get("artifact_uri")),
            "qa_status": _clean_text(raw.get("qa_status")),
        },
        "bom_component_context": _build_bom_component_context(raw),
        "published_seed_assets": _build_published_seed_assets(raw),
        "component_risk_overview": raw.get("component_risk_overview") or {},
        "primary_cvss_base_score": _coerce_float(raw.get("primary_cvss_base_score")),
        "primary_cvss_vector": _clean_text(raw.get("primary_cvss_vector")),
        "primary_cvss_severity_label": _clean_text(raw.get("primary_cvss_severity_label")),
        "active": bool(raw.get("active", False)),
        "family_inference_signals": family_inference_signals,
    }
    risk_flags = _build_risk_flags(normalized)
    audit_log = list(state.get("audit_log", []))
    audit_log.append(
        {
            "event": "intel_normalized",
            "attack_id": normalized["attack_id"],
            "attack_family": attack_family,
            "family_inference_signals": family_inference_signals,
            "risk_flags": risk_flags,
        }
    )
    return {
        "intel_normalized": normalized,
        "attack_family": attack_family,
        "risk_flags": risk_flags,
        "audit_log": audit_log,
    }
