"""Tests for Phase 5 — BOM resolution (rules-only + LLM-primary).

Covers:
    1. Rules-only path: alias resolution, version normalization
    2. Rules-only path: vendor platform aliases, seeded aliases
    3. Rules-only path: unresolved queue handling
    4. Rules-only path: DB fallback observability
    5. Reviewer: escalates ambiguous fuzzy resolution
    6. Reviewer: prefers alias candidate over embedding
    7. Reviewer: skips heuristic downgrades for LLM-accepted resolutions
    8. Confidence scoring: BOM resolution signal
    9. LLM-primary path: mocked LLM accept
   10. LLM-primary path: mocked LLM review_queue
   11. LLM-primary path: mocked LLM no_match
   12. LLM-primary path: audit records produced
   13. LLM-primary path: llm_required + LLM failure → raises
   14. LLM-primary path: llm_optional + LLM failure → rules fallback
   15. Node integration: resolve_ai_bom_node handles new signature
   16. Runtime integration: emits bom_resolutions and confidence_breakdown
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

BomMapperAgent = import_module(
    "agents.intel_agents.agents.bom_mapper_agent"
).BomMapperAgent
BomResolutionReviewerAgent = import_module(
    "agents.intel_agents.agents.bom_resolution_reviewer_agent"
).BomResolutionReviewerAgent
ConfidenceScoringService = import_module(
    "agents.intel_agents.services.confidence_scoring_service"
).ConfidenceScoringService
AiComponentSeedService = import_module(
    "db.services.component_seed_service"
).AiComponentSeedService
ComponentResolutionService = import_module(
    "agents.intel_agents.services.component_resolution_service"
).ComponentResolutionService
Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime
LlmBomResolutionAuditDTO = import_module(
    "agents.intel_agents.schemas.intel"
).LlmBomResolutionAuditDTO
resolve_ai_bom_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).resolve_ai_bom_node
build_initial_state = import_module(
    "agents.intel_agents.orchestrator.state"
).build_initial_state
RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO


def _item_with_bom(
    name: str, vendor: str | None = None, version: str | None = None
) -> dict:
    return {
        "raw_id": "raw-phase5",
        "attack_code": "ATTACK-PHASE5",
        "canonical_name": "Prompt Injection with Component Abuse",
        "attack_family": "prompt_injection",
        "severity_level": "high",
        "summary": "Prompt injection impacts an orchestration component.",
        "description": "Prompt injection impacts an orchestration component and its plugin stack.",
        "artifact_ref": "artifact://raw-phase5",
        "evidence_refs": ["artifact://raw-phase5", "https://example.com/raw-phase5"],
        "source_confidence": 0.88,
        "extraction_confidence": 0.84,
        "conflict_flags": [],
        "bom_mentions": [
            {
                "mentioned_name": name,
                "mentioned_vendor": vendor,
                "mentioned_version": version,
                "confidence_score": 0.81,
                "reason_code": "name_mention",
            }
        ],
        "source_metadata": {
            "source_name": "github_advisories",
            "source_coverage": ["github_advisories", "nvd"],
        },
        "dedup_decision": "new",
        "merge_audit_ref": "audit-1",
    }


# ---------------------------------------------------------------------------
# Helper: build a mock LLM decision dict
# ---------------------------------------------------------------------------


def _mock_llm_decision(
    *,
    component_code: str | None = "CMP-LANGCHAIN",
    component_name: str = "LangChain",
    component_layer: str = "framework",
    vendor_name: str | None = "LangChain",
    version_constraint_raw: str | None = None,
    normalized_version_constraint: str | None = None,
    decision: str = "accept",
    confidence: float = 0.92,
    evidence_quotes: list[str] | None = None,
    reasoning_summary: str = "Exact alias match from candidate list.",
) -> dict[str, Any]:
    return {
        "selected_component": {
            "component_code": component_code,
            "component_name": component_name,
            "component_layer": component_layer,
            "vendor_name": vendor_name,
        },
        "version_constraint_raw": version_constraint_raw,
        "normalized_version_constraint": normalized_version_constraint,
        "decision": decision,
        "confidence": confidence,
        "evidence_quotes": evidence_quotes or ["Prompt injection impacts LangChain"],
        "reasoning_summary": reasoning_summary,
        "candidate_ranking": [component_code or component_name],
    }


# ===========================================================================
# Rules-only path tests (backward compatibility)
# ===========================================================================


def test_phase5_bom_mapper_resolves_alias_and_normalizes_version() -> None:
    agent = BomMapperAgent(strategy="rules_only")
    items, audits = agent.resolve_batch(
        [_item_with_bom("Lang Chain", version="before 0.1.0")]
    )

    resolution = items[0]["bom_resolutions"][0]
    assert resolution["resolution_status"] == "resolved"
    assert resolution["selected_component"]["component_name"] == "LangChain"
    assert resolution["normalized_version_constraint"] == "<0.1.0"
    # Audits should be produced even in rules-only mode
    assert len(audits) >= 1
    assert audits[0]["strategy_executed"] == "rules_only"


def test_phase5_component_seed_catalog_covers_major_aliases() -> None:
    seeds = AiComponentSeedService.default_seeds()
    component_codes = {row["component_code"] for row in seeds}
    layers = {row["layer"] for row in seeds}

    assert "CMP-OPENAI-API" in component_codes
    assert "CMP-ANTHROPIC-API" in component_codes
    assert "CMP-HF-TRANSFORMERS" in component_codes
    assert "CMP-AZURE-OPENAI" in component_codes
    assert "CMP-BEDROCK" in component_codes
    assert layers == {
        "vendor_platform",
        "model_family",
        "framework",
        "plugin",
        "runtime",
        "vector_stack",
    }
    assert any(
        alias["alias_name"] == "chatgpt api"
        for row in seeds
        if row["component_code"] == "CMP-OPENAI-API"
        for alias in row["aliases"]
    )


def test_phase5_component_seed_catalog_includes_rich_metadata() -> None:
    seeds = {
        row["component_code"]: row for row in AiComponentSeedService.default_seeds()
    }

    assert seeds["CMP-OPENAI-API"]["purl"] == "pkg:pypi/openai"
    assert seeds["CMP-OPENAI-API"]["homepage_uri"] == "https://platform.openai.com/"
    assert seeds["CMP-LLAMA-MODELS"]["modality"] == "text"
    assert seeds["CMP-QDRANT"]["homepage_uri"] == "https://qdrant.tech/"
    assert seeds["CMP-LANGGRAPH"]["layer"] == "runtime"


def test_phase5_bom_mapper_reduces_review_queue_for_seeded_aliases() -> None:
    agent = BomMapperAgent(strategy="rules_only")
    items, audits = agent.resolve_batch(
        [
            _item_with_bom("Claude SDK", vendor="Anthropic"),
            _item_with_bom("transformers library", vendor="HuggingFace"),
            _item_with_bom("chromadb"),
        ]
    )

    resolutions = [item["bom_resolutions"][0] for item in items]
    queue_count = sum(
        1
        for item in items
        for r in item.get("bom_resolutions", [])
        if r["resolution_status"] != "resolved"
    )
    assert queue_count == 0
    assert [row["selected_component"]["component_name"] for row in resolutions] == [
        "Anthropic API",
        "HuggingFace Transformers",
        "Chroma",
    ]


def test_phase5_bom_mapper_handles_vendor_platform_aliases() -> None:
    agent = BomMapperAgent(strategy="rules_only")
    items, audits = agent.resolve_batch(
        [
            _item_with_bom("azure open ai", vendor="Microsoft"),
            _item_with_bom("amazon bedrock", vendor="AWS"),
            _item_with_bom("vertex ai studio", vendor="Google"),
        ]
    )

    resolutions = [item["bom_resolutions"][0] for item in items]
    queue_count = sum(
        1
        for item in items
        for r in item.get("bom_resolutions", [])
        if r["resolution_status"] != "resolved"
    )
    assert queue_count == 0
    assert [row["selected_component"]["component_name"] for row in resolutions] == [
        "Azure OpenAI",
        "Amazon Bedrock",
        "Vertex AI",
    ]


def test_phase5_bom_mapper_keeps_unresolved_queue_summary() -> None:
    agent = BomMapperAgent(strategy="rules_only")
    items, audits = agent.resolve_batch(
        [_item_with_bom("mystery orchestration shard", version="release train alpha")]
    )

    resolution = items[0]["bom_resolutions"][0]
    summary = items[0]["source_metadata"]["bom_resolution_summary"]
    queue_count = sum(
        1
        for item in items
        for r in item.get("bom_resolutions", [])
        if r["resolution_status"] != "resolved"
    )
    assert queue_count == 1
    assert resolution["resolution_status"] in {"review_queue", "unresolved"}
    assert summary["unresolved_mentions"]
    assert (
        summary["unresolved_mentions"][0]["mentioned_name"]
        == "mystery orchestration shard"
    )


def test_phase5_db_fallback_is_observable_when_db_path_fails() -> None:
    service = ComponentResolutionService()
    original_uow = service.resolve_item.__globals__["UnitOfWork"]
    original_resolve_item = service._resolve_item

    def _fake_resolve_item(item: dict, uow) -> tuple[dict, int]:
        return {**item, "source_metadata": {**item.get("source_metadata", {})}}, 0

    class _BoomUnitOfWork:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("db path exploded")

    service._resolve_item = _fake_resolve_item  # type: ignore[method-assign]
    service.resolve_item.__globals__["UnitOfWork"] = _BoomUnitOfWork
    try:
        resolved, _ = service.resolve_item(_item_with_bom("LangChain"))
    finally:
        service._resolve_item = original_resolve_item  # type: ignore[method-assign]
        service.resolve_item.__globals__["UnitOfWork"] = original_uow

    assert resolved["source_metadata"]["bom_resolution_db_fallback"]["active"] is True
    assert (
        resolved["source_metadata"]["bom_resolution_db_fallback"]["error_type"]
        == "RuntimeError"
    )


# ===========================================================================
# Reviewer tests
# ===========================================================================


def test_phase5_reviewer_escalates_ambiguous_fuzzy_resolution() -> None:
    reviewer = BomResolutionReviewerAgent()
    reviewed = reviewer.review_resolution(
        {
            "mentioned_name": "plugin",
            "mentioned_vendor": None,
            "mentioned_version": None,
            "normalized_alias": "plugin",
            "normalized_vendor": None,
            "normalized_version_constraint": None,
            "resolution_status": "resolved",
            "selected_component": {
                "component_name": "Retrieval Plugin",
                "vendor_name": None,
                "match_mode": "trigram",
                "final_score": 0.79,
            },
            "candidate_components": [
                {
                    "component_name": "Retrieval Plugin",
                    "vendor_name": None,
                    "match_mode": "trigram",
                    "match_score": 0.79,
                    "vendor_score": 0.0,
                    "final_score": 0.79,
                    "aliases": ["plugin"],
                    "reasons": [],
                },
                {
                    "component_name": "Agent Runtime",
                    "vendor_name": None,
                    "match_mode": "embedding",
                    "match_score": 0.76,
                    "vendor_score": 0.0,
                    "final_score": 0.76,
                    "aliases": ["agent workflow"],
                    "reasons": [],
                },
            ],
            "match_mode": "trigram",
            "match_confidence": 0.79,
            "reason_codes": [],
            "queue_ref": None,
            "review": None,
        }
    )

    assert reviewed["resolution_status"] == "review_queue"
    assert reviewed["review"]["decision"] == "review_queue"


def test_phase5_reviewer_prefers_alias_candidate_over_embedding_candidate() -> None:
    reviewer = BomResolutionReviewerAgent()
    reviewed = reviewer.review_resolution(
        {
            "mentioned_name": "azure open ai",
            "mentioned_vendor": "Microsoft",
            "mentioned_version": None,
            "normalized_alias": "azureopenai",
            "normalized_vendor": "microsoft",
            "normalized_version_constraint": None,
            "resolution_status": "resolved",
            "selected_component": {
                "component_name": "OpenAI API",
                "vendor_name": "OpenAI",
                "match_mode": "embedding",
                "final_score": 0.83,
            },
            "candidate_components": [
                {
                    "component_name": "OpenAI API",
                    "vendor_name": "OpenAI",
                    "match_mode": "embedding",
                    "match_score": 0.83,
                    "vendor_score": 0.0,
                    "final_score": 0.83,
                    "aliases": ["openai sdk"],
                    "reasons": [],
                },
                {
                    "component_name": "Azure OpenAI",
                    "vendor_name": "Microsoft",
                    "match_mode": "alias",
                    "match_score": 0.9,
                    "vendor_score": 0.08,
                    "final_score": 0.98,
                    "aliases": ["azure open ai"],
                    "reasons": [],
                },
            ],
            "match_mode": "embedding",
            "match_confidence": 0.83,
            "reason_codes": ["fuzzy_match:embedding"],
            "queue_ref": None,
            "review": None,
        }
    )

    assert reviewed["review"]["decision"] == "revise"
    assert reviewed["selected_component"]["component_name"] == "Azure OpenAI"


def test_phase5_reviewer_skips_heuristic_downgrades_for_llm_accepts() -> None:
    """Reviewer should NOT apply fuzzy-threshold or candidate-gap downgrades
    when the resolution was made by LLM with high confidence."""
    reviewer = BomResolutionReviewerAgent()
    reviewed = reviewer.review_resolution(
        {
            "mentioned_name": "langchain framework",
            "mentioned_vendor": None,
            "mentioned_version": None,
            "normalized_alias": "langchainframework",
            "normalized_vendor": None,
            "normalized_version_constraint": None,
            "resolution_status": "resolved",
            "selected_component": {
                "component_name": "LangChain",
                "vendor_name": "LangChain",
                "match_mode": "trigram",
                "final_score": 0.78,
            },
            "candidate_components": [
                {
                    "component_name": "LangChain",
                    "vendor_name": "LangChain",
                    "match_mode": "trigram",
                    "match_score": 0.78,
                    "vendor_score": 0.0,
                    "final_score": 0.78,
                    "aliases": ["langchain"],
                    "reasons": [],
                },
                {
                    "component_name": "LangGraph",
                    "vendor_name": "LangChain",
                    "match_mode": "trigram",
                    "match_score": 0.76,
                    "vendor_score": 0.0,
                    "final_score": 0.76,
                    "aliases": ["langgraph"],
                    "reasons": [],
                },
            ],
            "match_mode": "trigram",
            "match_confidence": 0.91,
            "reason_codes": [
                "llm_reason:LangChain is the primary framework mentioned",
            ],
            "queue_ref": None,
            "review": None,
        }
    )

    # With LLM-aware reason_codes and high match_confidence, reviewer should keep it accepted
    assert reviewed["resolution_status"] == "resolved"
    assert reviewed["review"]["decision"] == "accept"


# ===========================================================================
# Confidence scoring
# ===========================================================================


def test_phase5_confidence_scoring_uses_bom_resolution_signal() -> None:
    service = ConfidenceScoringService()
    scored = service.score_items(
        [
            _item_with_bom("LangChain")
            | {
                "bom_resolutions": [
                    {
                        "resolution_status": "resolved",
                        "match_confidence": 0.94,
                        "review": {"decision": "accept"},
                    }
                ]
            }
        ],
        dedup_decisions=[
            {"merge_audit_ref": "audit-1", "decision": "new", "similarity_score": 0.2}
        ],
        source_quality_rows=[{"source_name": "github_advisories", "trust_level": 0.91}],
    )

    first = scored[0]
    assert first["confidence_breakdown"]["bom_resolution_confidence"] >= 0.9
    assert first["confidence_score"] > 0.8


# ===========================================================================
# LLM-primary path tests (mocked LLM)
# ===========================================================================


def test_phase5_llm_primary_accept_produces_resolved_resolution() -> None:
    """LLM returns accept decision → resolution_status should be 'resolved'."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.PROMPT_VERSION = "v1.0-test"
    mock_llm.resolve.return_value = _mock_llm_decision(
        component_code="CMP-LANGCHAIN",
        component_name="LangChain",
        component_layer="framework",
        decision="accept",
        confidence=0.93,
        normalized_version_constraint="<0.1.0",
    )

    agent = BomMapperAgent(strategy="rules_only")  # avoid LLM init
    agent.strategy = "llm_required"
    agent._llm = mock_llm

    items, audits = agent.resolve_batch(
        [_item_with_bom("Lang Chain", version="before 0.1.0")]
    )

    assert len(items) == 1
    res = items[0]["bom_resolutions"][0]
    assert res["resolution_status"] == "resolved"
    assert res["selected_component"]["component_name"] == "LangChain"
    assert res["normalized_version_constraint"] == "<0.1.0"

    # Audit should record LLM details
    assert len(audits) == 1
    audit = audits[0]
    assert audit["strategy_executed"] == "llm_primary"
    assert audit["llm_confidence"] == 0.93
    assert audit["llm_decision"] == "accept"


def test_phase5_llm_primary_review_queue_produces_queued_resolution() -> None:
    """LLM returns review_queue → resolution_status should be 'review_queue'."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.PROMPT_VERSION = "v1.0-test"
    mock_llm.resolve.return_value = _mock_llm_decision(
        component_code="CMP-LANGCHAIN",
        component_name="LangChain",
        decision="review_queue",
        confidence=0.55,
        reasoning_summary="Multiple candidates with similar scores.",
    )

    agent = BomMapperAgent(strategy="rules_only")
    agent.strategy = "llm_required"
    agent._llm = mock_llm

    items, audits = agent.resolve_batch([_item_with_bom("langchain or langgraph")])

    res = items[0]["bom_resolutions"][0]
    assert res["resolution_status"] == "review_queue"

    summary = items[0]["source_metadata"]["bom_resolution_summary"]
    assert summary["queued"] == 1
    assert len(summary["unresolved_mentions"]) == 1


def test_phase5_llm_primary_no_match_produces_unresolved() -> None:
    """LLM returns no_match → resolution_status should be 'unresolved'."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.PROMPT_VERSION = "v1.0-test"
    no_match = _mock_llm_decision(
        component_code=None,
        component_name="unknown",
        decision="no_match",
        confidence=0.2,
        reasoning_summary="No suitable candidate found.",
    )
    no_match["selected_component"] = None
    mock_llm.resolve.return_value = no_match

    agent = BomMapperAgent(strategy="rules_only")
    agent.strategy = "llm_required"
    agent._llm = mock_llm

    items, audits = agent.resolve_batch([_item_with_bom("mystery shard v99")])

    res = items[0]["bom_resolutions"][0]
    assert res["resolution_status"] == "unresolved"
    assert audits[0]["llm_decision"] == "no_match"


def test_phase5_llm_primary_audit_records_are_well_formed() -> None:
    """Verify audit records contain all required fields."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.PROMPT_VERSION = "v1.0-test"
    mock_llm.resolve.return_value = _mock_llm_decision(
        component_code="CMP-OPENAI-API",
        component_name="OpenAI API",
        component_layer="vendor_platform",
        vendor_name="OpenAI",
        decision="accept",
        confidence=0.95,
    )

    agent = BomMapperAgent(strategy="rules_only")
    agent.strategy = "llm_required"
    agent._llm = mock_llm
    agent.llm_model = "qwen-max"

    items, audits = agent.resolve_batch([_item_with_bom("openai api", vendor="OpenAI")])

    assert len(audits) == 1
    audit = audits[0]
    # Validate via DTO
    validated = LlmBomResolutionAuditDTO.model_validate(audit)
    assert validated.raw_id == "raw-phase5"
    assert validated.mention_index == 0
    assert validated.mentioned_name == "openai api"
    assert validated.strategy_requested in {
        "llm_required",
        "llm_optional",
        "rules_only",
        "rules_only_degraded",
    }
    assert validated.strategy_executed == "llm_primary"
    assert validated.llm_model == "qwen-max"
    assert validated.prompt_version == "v1.0-test"
    assert validated.llm_confidence == 0.95
    assert validated.llm_decision == "accept"
    assert validated.candidate_count >= 0
    assert validated.invoked_at is not None


def test_phase5_llm_required_failure_raises() -> None:
    """When strategy is llm_required and LLM fails, a RuntimeError must be raised."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = False
    mock_llm.PROMPT_VERSION = "v1.0-test"

    agent = BomMapperAgent(strategy="rules_only")
    agent.strategy = "llm_required"
    agent._llm = mock_llm

    import pytest

    with pytest.raises(RuntimeError, match="LLM BOM resolution required but failed"):
        agent.resolve_batch([_item_with_bom("LangChain")])


def test_phase5_llm_optional_failure_falls_back_to_rules() -> None:
    """When strategy is llm_optional and LLM fails, should fall back to rules."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = False
    mock_llm.PROMPT_VERSION = "v1.0-test"

    agent = BomMapperAgent(strategy="rules_only")
    agent.strategy = "llm_optional"
    agent._llm = mock_llm

    items, audits = agent.resolve_batch([_item_with_bom("LangChain")])

    # Should succeed via rules fallback
    res = items[0]["bom_resolutions"][0]
    assert res["resolution_status"] == "resolved"
    assert res["selected_component"]["component_name"] == "LangChain"

    # Audit should record degraded fallback
    assert len(audits) == 1
    assert audits[0]["strategy_executed"] == "rules_only_degraded"
    assert audits[0]["fallback_reason"] is not None
    assert "llm_failed" in audits[0]["fallback_reason"]


def test_phase5_llm_primary_multi_mention_batch() -> None:
    """LLM-primary path with multiple items, each with a bom_mention."""
    mock_llm = MagicMock()
    mock_llm.is_available.return_value = True
    mock_llm.PROMPT_VERSION = "v1.0-test"

    no_match_decision = _mock_llm_decision(
        decision="no_match",
        confidence=0.15,
        component_name="unknown",
        component_code=None,
        reasoning_summary="No candidate matches the vague mention.",
    )
    no_match_decision["selected_component"] = None

    # Return different decisions for different calls
    mock_llm.resolve.side_effect = [
        _mock_llm_decision(
            component_name="LangChain",
            component_code="CMP-LANGCHAIN",
            decision="accept",
            confidence=0.92,
        ),
        _mock_llm_decision(
            component_name="OpenAI API",
            component_code="CMP-OPENAI-API",
            decision="accept",
            confidence=0.96,
        ),
        no_match_decision,
    ]

    agent = BomMapperAgent(strategy="rules_only")
    agent.strategy = "llm_required"
    agent._llm = mock_llm

    items, audits = agent.resolve_batch(
        [
            _item_with_bom("langchain"),
            _item_with_bom("openai", vendor="OpenAI"),
            _item_with_bom("totally unknown thing"),
        ]
    )

    assert len(items) == 3
    assert items[0]["bom_resolutions"][0]["resolution_status"] == "resolved"
    assert items[1]["bom_resolutions"][0]["resolution_status"] == "resolved"
    assert items[2]["bom_resolutions"][0]["resolution_status"] == "unresolved"
    assert len(audits) == 3


# ===========================================================================
# Node integration
# ===========================================================================


def test_phase5_resolve_ai_bom_node_handles_new_signature() -> None:
    """The resolve_ai_bom_node should use BomMapperAgent with strategy from
    runtime_context and handle the tuple return signature."""
    ctx = RuntimeContextDTO.default_stub()
    state = build_initial_state(
        runtime_context=ctx.model_dump(mode="python"),
    )
    state["standardized_items"] = [
        _item_with_bom("LangChain"),
        _item_with_bom("openai sdk", vendor="OpenAI"),
    ]

    result = resolve_ai_bom_node(state)

    assert "standardized_items" in result
    assert "llm_bom_resolution_audits" in result
    assert "bom_queue_count" in result
    assert isinstance(result["standardized_items"], list)
    assert isinstance(result["llm_bom_resolution_audits"], list)
    for item in result["standardized_items"]:
        assert "bom_resolutions" in item


def test_phase5_resolve_ai_bom_node_emits_audits_to_state() -> None:
    """The node should emit llm_bom_resolution_audits that merge into state."""
    ctx = RuntimeContextDTO.default_stub()
    state = build_initial_state(
        runtime_context=ctx.model_dump(mode="python"),
    )
    state["standardized_items"] = [_item_with_bom("LangChain")]

    result = resolve_ai_bom_node(state)

    audits = result.get("llm_bom_resolution_audits", [])
    assert isinstance(audits, list)
    assert len(audits) >= 1
    # Each audit should be validatable
    for audit in audits:
        LlmBomResolutionAuditDTO.model_validate(audit)


# ===========================================================================
# Runtime integration
# ===========================================================================


def test_phase5_runtime_emits_bom_resolutions_and_confidence_breakdown() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run()

    assert result["run_status"] == "succeeded"
    assert result["standardized_items"]
    first = result["standardized_items"][0]
    assert "bom_resolutions" in first
    assert "confidence_breakdown" in first


def test_phase5_runtime_state_contains_llm_bom_resolution_audits() -> None:
    """Verify that the runtime state includes the llm_bom_resolution_audits field."""
    state = build_initial_state()
    assert "llm_bom_resolution_audits" in state
    assert state["llm_bom_resolution_audits"] == []
