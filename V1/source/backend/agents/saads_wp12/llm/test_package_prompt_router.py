from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.agents.saads_wp12.engines.test_package_generation import TestPackageGenerationInputContract


PROMPT_MODES = {
    "single_family",
    "family_plus_taxonomy",
    "multi_taxonomy_composite",
    "analysis_only",
}


@dataclass(frozen=True, slots=True)
class PromptRouteDecision:
    prompt_mode: str
    selected_family: str
    selected_primary_taxonomy: str
    selected_secondary_taxonomies: tuple[str, ...]
    selected_few_shot_labels: tuple[str, ...]
    routing_rationale: tuple[str, ...]
    routing_policy: tuple[str, ...]

    def to_payload(self, mode_guidance: dict[str, Any]) -> dict[str, Any]:
        payload = asdict(self)
        payload["prompt_mode_guidance"] = mode_guidance
        payload["selected_secondary_taxonomies"] = list(self.selected_secondary_taxonomies)
        payload["selected_few_shot_labels"] = list(self.selected_few_shot_labels)
        payload["routing_rationale"] = list(self.routing_rationale)
        payload["routing_policy"] = list(self.routing_policy)
        return payload


@dataclass(frozen=True, slots=True)
class RouteSignalSnapshot:
    attack_family: str
    generation_route: str
    primary_taxonomy_code: str
    ranked_taxonomy_codes: tuple[str, ...]
    execution_eligibility: str
    should_execute: bool
    classification_basis: str
    scenario_text: str

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ranked_taxonomy_codes"] = list(self.ranked_taxonomy_codes)
        return payload


def extract_route_signal_snapshot(
    contract: TestPackageGenerationInputContract,
) -> RouteSignalSnapshot:
    evidence_and_context = contract.evidence_and_context or {}
    classification_rationale = (
        evidence_and_context.get("classification_rationale")
        or contract.classification_rationale
        or {}
    )
    primary_taxonomy_code, ranked_taxonomy_codes = extract_taxonomy_context(contract)
    attack_family = (
        contract.attack_family
        or str((contract.threat_profile or {}).get("attack_family") or "")
        or str(classification_rationale.get("top_candidate") or "")
        or "prompt_injection"
    )
    execution_assessment = contract.execution_assessment or {}
    execution_eligibility = str(execution_assessment.get("execution_eligibility") or "")
    should_execute = bool(execution_assessment.get("should_execute"))
    classification_basis = "classification_rationale"
    if not classification_rationale:
        classification_basis = "taxonomy_context"
    if not ranked_taxonomy_codes:
        classification_basis = "fallback_defaults"
    threat_understanding = contract.threat_understanding or {}
    attack_entry_context = threat_understanding.get("attack_entry_context") or {}
    scenario_text = " ".join(
        str(value)
        for value in [
            contract.target_surface or "",
            (contract.threat_profile or {}).get("threat_summary", ""),
            threat_understanding.get("threat_summary", ""),
            threat_understanding.get("attack_mechanism", ""),
            attack_entry_context.get("description", ""),
            threat_understanding.get("recommended_test_strategy", ""),
        ]
        if str(value).strip()
    ).lower()

    return RouteSignalSnapshot(
        attack_family=attack_family,
        generation_route=contract.generation_route or attack_family,
        primary_taxonomy_code=primary_taxonomy_code,
        ranked_taxonomy_codes=tuple(ranked_taxonomy_codes),
        execution_eligibility=execution_eligibility,
        should_execute=should_execute,
        classification_basis=classification_basis,
        scenario_text=scenario_text,
    )


def extract_taxonomy_context(
    contract: TestPackageGenerationInputContract,
) -> tuple[str, list[str]]:
    evidence_and_context = contract.evidence_and_context or {}
    taxonomy_context = contract.evidence_and_context.get("taxonomy_context", {})
    primary_taxonomy_code = ""
    all_taxonomy_codes: list[str] = []

    ranked_taxonomy_codes = _rank_taxonomy_codes_from_threat_understanding(contract)
    if ranked_taxonomy_codes:
        all_taxonomy_codes = ranked_taxonomy_codes.copy()

    if isinstance(taxonomy_context, dict):
        primary_entry = taxonomy_context.get("primary") or {}
        if isinstance(primary_entry, dict):
            primary_taxonomy_code = str(primary_entry.get("code") or "")
        if not primary_taxonomy_code:
            primary_taxonomy_code = str(
                taxonomy_context.get("selected_taxonomy_code") or ""
            )
        raw_codes = taxonomy_context.get("all_taxonomy_codes") or []
        if isinstance(raw_codes, list) and not all_taxonomy_codes:
            all_taxonomy_codes = [str(code) for code in raw_codes if str(code).strip()]

    if not primary_taxonomy_code:
        classification_rationale = evidence_and_context.get("classification_rationale") or {}
        primary_taxonomy_code = str(classification_rationale.get("taxonomy_signal") or "")

    return primary_taxonomy_code, all_taxonomy_codes


def _rank_taxonomy_codes_from_threat_understanding(
    contract: TestPackageGenerationInputContract,
) -> list[str]:
    evidence_and_context = contract.evidence_and_context or {}
    classification_rationale = evidence_and_context.get("classification_rationale") or {}
    ranked_signals = classification_rationale.get("all_taxonomy_signals") or []
    if isinstance(ranked_signals, list) and ranked_signals:
        normalized: list[tuple[int, float, str]] = []
        for item in ranked_signals:
            if not isinstance(item, dict):
                continue
            code = str(item.get("taxonomy_code") or "").strip()
            if not code:
                continue
            is_primary = 0 if bool(item.get("is_primary")) else 1
            confidence = float(item.get("confidence_score") or 0.0)
            normalized.append((is_primary, -confidence, code))
        if normalized:
            normalized.sort()
            return [code for _, _, code in normalized]

    threat_understanding = contract.threat_understanding or {}
    all_taxonomies = threat_understanding.get("all_taxonomies") or []
    if isinstance(all_taxonomies, list) and all_taxonomies:
        normalized = []
        for item in all_taxonomies:
            if not isinstance(item, dict):
                continue
            code = str(item.get("taxonomy_code") or item.get("code") or "").strip()
            if not code:
                continue
            is_primary = 0 if bool(item.get("is_primary")) else 1
            confidence = float(item.get("confidence_score") or 0.0)
            normalized.append((is_primary, -confidence, code))
        if normalized:
            normalized.sort()
            return [code for _, _, code in normalized]

    return []


def select_secondary_taxonomy_codes(
    snapshot: RouteSignalSnapshot,
    all_taxonomy_codes: list[str],
    available_taxonomy_codes: set[str],
    *,
    family_few_shot_labels: dict[str, list[str]] | None = None,
    primary_taxonomy_few_shot_labels: dict[str, list[str]] | None = None,
    secondary_taxonomy_few_shot_labels: dict[str, list[str]] | None = None,
    max_secondary: int = 2,
) -> list[str]:
    candidates = [
        code
        for code in all_taxonomy_codes
        if code and code != snapshot.primary_taxonomy_code and code in available_taxonomy_codes
    ]
    if not candidates:
        return []

    family_priority = {
        "prompt_injection": {
            "OWASP-LLM-02": 0.45,
            "OWASP-LLM-05": 0.30,
            "OWASP-LLM-08": 0.25,
            "OWASP-LLM-07": 0.15,
            "OWASP-LLM-06": 0.12,
            "OWASP-LLM-03": 0.10,
        },
        "tool_hijack": {
            "OWASP-LLM-03": 0.40,
            "OWASP-LLM-06": 0.35,
            "OWASP-LLM-05": 0.22,
            "OWASP-LLM-02": 0.10,
            "OWASP-LLM-07": 0.08,
        },
        "long_horizon_dialogue": {
            "OWASP-LLM-09": 0.35,
            "OWASP-LLM-04": 0.25,
            "OWASP-LLM-07": 0.10,
        },
    }

    scenario_keyword_boosts = {
        "OWASP-LLM-02": [
            "render",
            "downstream",
            "output",
            "execute",
            "exfiltrate",
            "response",
        ],
        "OWASP-LLM-03": ["plugin", "connector", "mcp", "parameter", "tool call"],
        "OWASP-LLM-05": [
            "workflow",
            "builder",
            "dependency",
            "artifact",
            "component",
            "docker",
            "metadata api",
            "http tool",
            "internal service",
        ],
        "OWASP-LLM-06": [
            "approval",
            "privilege",
            "self-modification",
            "memory",
            "autonomous",
        ],
        "OWASP-LLM-07": ["hidden instruction", "system prompt", "leak", "disclose"],
        "OWASP-LLM-08": ["retrieval", "chunk", "embedding", "vector"],
        "OWASP-LLM-09": ["confidence", "verification", "decision"],
        "OWASP-LLM-10": ["quota", "budget", "spend", "retry"],
    }

    few_shot_support = secondary_taxonomy_few_shot_labels or {}
    primary_support = primary_taxonomy_few_shot_labels or {}
    family_support = family_few_shot_labels or {}
    scenario_text = snapshot.scenario_text
    family = snapshot.attack_family

    scored: list[tuple[float, int, str]] = []
    for rank_index, code in enumerate(candidates):
        score = 1.0 - (rank_index * 0.1)
        score += family_priority.get(family, {}).get(code, 0.0)
        score += min(len(few_shot_support.get(code, [])) * 0.08, 0.16)
        score += min(len(primary_support.get(code, [])) * 0.04, 0.08)
        score += min(len(family_support.get(family, [])) * 0.01, 0.03)
        keyword_hits = sum(
            1 for keyword in scenario_keyword_boosts.get(code, []) if keyword in scenario_text
        )
        score += min(keyword_hits * 0.12, 0.36)
        scored.append((score, rank_index, code))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [code for _, _, code in scored[:max_secondary]]


def infer_prompt_mode(
    snapshot: RouteSignalSnapshot,
    *,
    secondary_taxonomy_codes: list[str],
) -> str:
    family = snapshot.attack_family or "prompt_injection"
    execution_eligibility = snapshot.execution_eligibility

    if family == "unsupported" or snapshot.generation_route == "unsupported":
        return "analysis_only"
    if execution_eligibility == "do_not_execute":
        return "analysis_only"
    if secondary_taxonomy_codes:
        return "multi_taxonomy_composite"
    if snapshot.primary_taxonomy_code:
        return "family_plus_taxonomy"
    return "single_family"


def select_few_shot_labels(
    *,
    family: str,
    prompt_mode: str,
    primary_taxonomy_code: str,
    secondary_taxonomy_codes: list[str],
    family_few_shot_labels: dict[str, list[str]],
    primary_taxonomy_few_shot_labels: dict[str, list[str]],
    secondary_taxonomy_few_shot_labels: dict[str, list[str]],
    max_examples: int = 4,
) -> list[str]:
    selected_labels: list[str] = []

    def _add(labels: list[str]) -> None:
        for label in labels:
            if label not in selected_labels:
                selected_labels.append(label)

    if prompt_mode == "analysis_only":
        return ["unsupported_triage"]

    _add(family_few_shot_labels.get(family, []))
    if prompt_mode in {"family_plus_taxonomy", "multi_taxonomy_composite"} and primary_taxonomy_code:
        _add(primary_taxonomy_few_shot_labels.get(primary_taxonomy_code, []))
    if prompt_mode == "multi_taxonomy_composite":
        for code in secondary_taxonomy_codes:
            _add(secondary_taxonomy_few_shot_labels.get(code, []))

    if not selected_labels:
        _add(family_few_shot_labels.get("prompt_injection", []))

    return selected_labels[:max_examples]


def build_prompt_route_decision(
    contract: TestPackageGenerationInputContract,
    *,
    available_taxonomy_codes: set[str],
    family_few_shot_labels: dict[str, list[str]],
    primary_taxonomy_few_shot_labels: dict[str, list[str]],
    secondary_taxonomy_few_shot_labels: dict[str, list[str]],
) -> PromptRouteDecision:
    snapshot = extract_route_signal_snapshot(contract)
    family = snapshot.attack_family or "prompt_injection"
    primary_taxonomy_code = snapshot.primary_taxonomy_code
    all_taxonomy_codes = list(snapshot.ranked_taxonomy_codes)
    secondary_taxonomy_codes = select_secondary_taxonomy_codes(
        snapshot,
        all_taxonomy_codes,
        available_taxonomy_codes,
        family_few_shot_labels=family_few_shot_labels,
        primary_taxonomy_few_shot_labels=primary_taxonomy_few_shot_labels,
        secondary_taxonomy_few_shot_labels=secondary_taxonomy_few_shot_labels,
    )
    prompt_mode = infer_prompt_mode(
        snapshot,
        secondary_taxonomy_codes=secondary_taxonomy_codes,
    )
    selected_few_shot_labels = select_few_shot_labels(
        family=family,
        prompt_mode=prompt_mode,
        primary_taxonomy_code=primary_taxonomy_code,
        secondary_taxonomy_codes=secondary_taxonomy_codes,
        family_few_shot_labels=family_few_shot_labels,
        primary_taxonomy_few_shot_labels=primary_taxonomy_few_shot_labels,
        secondary_taxonomy_few_shot_labels=secondary_taxonomy_few_shot_labels,
    )

    routing_rationale = [
        f"Family signal selected '{family}' as the primary planning spine.",
        f"Route signals were normalized from ThreatUnderstanding using '{snapshot.classification_basis}' as the main taxonomy source.",
    ]
    if prompt_mode == "analysis_only":
        routing_rationale.append(
            "Analysis-only route selected because the case is unsupported or execution should stay non-executable."
        )
    elif prompt_mode == "single_family":
        routing_rationale.append(
            "Single-family route selected because no meaningful taxonomy-specific split was available."
        )
    elif prompt_mode == "family_plus_taxonomy":
        routing_rationale.append(
            f"Family-plus-taxonomy route selected because primary taxonomy '{primary_taxonomy_code}' adds a narrower validation lens."
        )
    elif prompt_mode == "multi_taxonomy_composite":
        routing_rationale.append(
            "Composite route selected because the sample carries multiple meaningful taxonomy risk themes."
        )
    if primary_taxonomy_code:
        routing_rationale.append(f"Primary taxonomy retained: '{primary_taxonomy_code}'.")
    if secondary_taxonomy_codes:
        routing_rationale.append(
            "Secondary taxonomies retained for explicit evidence or follow-up patches: "
            + ", ".join(secondary_taxonomy_codes)
            + "."
        )
    routing_rationale.append(
        "Few-shot routing stayed selective so only the examples most relevant to the chosen route remain in scope."
    )

    return PromptRouteDecision(
        prompt_mode=prompt_mode,
        selected_family=family,
        selected_primary_taxonomy=primary_taxonomy_code,
        selected_secondary_taxonomies=tuple(secondary_taxonomy_codes),
        selected_few_shot_labels=tuple(selected_few_shot_labels),
        routing_rationale=tuple(routing_rationale),
        routing_policy=(
            "Layer 1: choose prompt_mode before assembling the prompt.",
            "Layer 2: choose family, taxonomy, and few-shot materials justified by that mode.",
            "Always include the common plan foundation.",
            "Include at most one primary taxonomy playbook and up to two secondary taxonomy patches.",
            "Keep few-shot routing selective instead of loading the full reference library.",
        ),
    )
