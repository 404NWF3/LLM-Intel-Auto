"""Tests for Phase 3 — LLM-primary standardization.

Covers:
    1. Rules-only path (backward compatibility)
    2. LLM-primary path with mocked LLM
    3. Degraded path (llm_optional + LLM failure)
    4. llm_required + LLM failure → raises
    5. RuleValidatorFuser standalone
    6. New DTO shapes
    7. Audit record production
    8. Field-level confidence from LLM
    9. Evidence spans pass-through
   10. Node-level integration (parse_and_standardize_node)
   11. Batch with multiple items
   12. Existing integration tests (Phase 2 → Phase 3 pipeline)
   13. Full runtime integration
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

StandardizerAgent = import_module(
    "agents.intel_agents.agents.standardizer_agent"
).StandardizerAgent
RuleValidatorFuser = import_module(
    "agents.intel_agents.tools.rule_validator_fuser"
).RuleValidatorFuser
LlmStandardizationAuditDTO = import_module(
    "agents.intel_agents.schemas.intel"
).LlmStandardizationAuditDTO
LlmExtractionEvidenceDTO = import_module(
    "agents.intel_agents.schemas.intel"
).LlmExtractionEvidenceDTO
LlmFieldConfidenceDTO = import_module(
    "agents.intel_agents.schemas.intel"
).LlmFieldConfidenceDTO
LLMStandardizationDecisionDTO = import_module(
    "agents.intel_agents.schemas.intel"
).LLMStandardizationDecisionDTO
StandardizedIntelDTO = import_module(
    "agents.intel_agents.schemas.intel"
).StandardizedIntelDTO
SourceCollectionCrew = import_module(
    "agents.intel_agents.crews.source_collection_crew"
).SourceCollectionCrew
SourceExecutionPlanDTO = import_module(
    "agents.intel_agents.schemas.plan"
).SourceExecutionPlanDTO
RawIngestFlow = import_module(
    "agents.intel_agents.services.raw_ingest_flow"
).RawIngestFlow
Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_item(*, tmpdir: Path, source_name: str = "nvd") -> dict[str, Any]:
    """Create a minimal raw item with a real payload file."""
    payload_content = json.dumps(
        {
            "cve": {
                "id": "CVE-2025-99999",
                "descriptions": [
                    {
                        "lang": "en",
                        "value": (
                            "LangChain prompt injection vulnerability allows "
                            "attackers to hijack agent tool execution via crafted "
                            "user input. High severity, CVSS 8.6."
                        ),
                    }
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {
                            "cvssData": {
                                "baseScore": 8.6,
                                "baseSeverity": "HIGH",
                            }
                        }
                    ]
                },
            }
        }
    )
    payload_path = tmpdir / "test_payload.json"
    payload_path.write_text(payload_content, encoding="utf-8")
    return {
        "query_run_id": "qr_test_001",
        "source_name": source_name,
        "source_uri": "https://example.com/cve/CVE-2025-99999",
        "external_id": "CVE-2025-99999",
        "title": "LangChain Prompt Injection",
        "summary": "Prompt injection in LangChain agent tooling",
        "author": None,
        "published_at": "2025-01-15T00:00:00Z",
        "fetched_at": "2025-03-15T00:00:00Z",
        "raw_format": "json",
        "artifact_ref": str(payload_path),
        "payload_uri": str(payload_path),
        "language_code": "en",
        "relevance_score": 0.95,
        "parser_status": "parsed",
        "metadata": {"query_text": "langchain prompt injection"},
        "content_hash": "a" * 64,
    }


def _make_mock_llm_result() -> dict[str, Any]:
    """Return a dict matching LlmStandardizationResult schema."""
    return {
        "canonical_name": "LangChain Agent Prompt Injection via Tool Hijack",
        "attack_family": "prompt_injection",
        "severity_level": "high",
        "summary": "Attackers inject malicious prompts to hijack LangChain agent tool execution.",
        "description": (
            "A prompt injection vulnerability in LangChain's agent runtime "
            "allows crafted user input to override system instructions and "
            "redirect tool calls to attacker-controlled endpoints."
        ),
        "exploit_preconditions": "Agent must have tool access and accept user-supplied prompts.",
        "impact_scope": "agent_runtime_and_downstream_tools",
        "extraction_reason": "CVE-2025-99999 describes a prompt injection targeting LangChain agent tooling.",
        "taxonomy_items": [
            {
                "taxonomy_type": "OWASP_LLM",
                "taxonomy_code": "OWASP-LLM-01",
                "taxonomy_name": "Prompt Injection",
                "confidence_score": 0.95,
                "is_primary": True,
            },
            {
                "taxonomy_type": "CWE",
                "taxonomy_code": "CWE-20",
                "taxonomy_name": "Improper Input Validation",
                "confidence_score": 0.80,
                "is_primary": False,
            },
        ],
        "cvss_hint": {
            "cvss_version": "3.1",
            "base_score": 8.6,
            "severity_label": "High",
            "score_origin": "supplied",
            "vector_string": None,
        },
        "bom_mentions": [
            {
                "mentioned_name": "langchain",
                "mentioned_vendor": "LangChain",
                "mentioned_version": None,
                "component_layer": "framework",
                "confidence_score": 0.92,
                "reason_code": "llm_inferred",
            }
        ],
        "evidence_spans": [
            {
                "field_name": "canonical_name",
                "evidence_text": "LangChain prompt injection vulnerability",
                "source_offset": None,
            },
            {
                "field_name": "attack_family",
                "evidence_text": "prompt injection vulnerability allows attackers to hijack",
                "source_offset": None,
            },
            {
                "field_name": "bom_mentions",
                "evidence_text": "LangChain",
                "source_offset": None,
            },
        ],
        "field_confidences": [
            {
                "field_name": "canonical_name",
                "confidence": 0.93,
                "reason": "Clear CVE title",
            },
            {
                "field_name": "attack_family",
                "confidence": 0.95,
                "reason": "Explicit prompt injection mention",
            },
            {
                "field_name": "severity_level",
                "confidence": 0.90,
                "reason": "CVSS 8.6 supplied",
            },
            {
                "field_name": "summary",
                "confidence": 0.88,
                "reason": "Derived from CVE description",
            },
            {
                "field_name": "bom_mentions",
                "confidence": 0.92,
                "reason": "LangChain explicitly named",
            },
        ],
        "overall_confidence": 0.91,
    }


def _make_mock_llm_standardizer(result: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock LLM standardizer that returns a canned result."""
    mock = MagicMock()
    mock.model = "qwen-max"
    mock.PROMPT_VERSION = "v2.0-llm-primary"
    mock.is_available.return_value = True
    mock.validate_connectivity.return_value = None
    mock.extract.return_value = result or _make_mock_llm_result()
    return mock


def _make_failing_llm_standardizer() -> MagicMock:
    """Create a mock LLM standardizer that raises on extract."""
    mock = MagicMock()
    mock.model = "qwen-max"
    mock.PROMPT_VERSION = "v2.0-llm-primary"
    mock.is_available.return_value = True
    mock.validate_connectivity.return_value = None
    mock.extract.side_effect = RuntimeError("LLM service unavailable")
    return mock


# ===========================================================================
# Test 1: Rules-only backward compatibility
# ===========================================================================


def test_rules_only_produces_valid_standardized_items(tmp_path: Path) -> None:
    raw_item = _make_raw_item(tmpdir=tmp_path)
    agent = StandardizerAgent(strategy="rules_only")
    items, audits = agent.standardize_batch([raw_item])

    assert len(items) == 1
    assert len(audits) == 1
    # Validate DTO shape
    StandardizedIntelDTO.model_validate(items[0])
    LlmStandardizationAuditDTO.model_validate(audits[0])
    assert items[0]["source_metadata"]["standardization_strategy"] == "rules_only"
    assert audits[0]["strategy_executed"] == "rules_only"
    assert audits[0]["llm_confidence"] == 0.0
    # Rich output fields present
    assert items[0]["attack_code"].startswith("ATTACK-")
    assert items[0]["taxonomy_items"]
    assert items[0]["stix_payload"]["type"] == "attack-pattern"
    assert items[0]["evidence_refs"]
    assert items[0]["extraction_reason"]
    assert items[0]["field_confidence"]
    assert "validation_findings" in items[0]


# ===========================================================================
# Test 2: LLM-primary path with mock
# ===========================================================================


def test_llm_primary_produces_enriched_output(tmp_path: Path) -> None:
    raw_item = _make_raw_item(tmpdir=tmp_path)
    mock_llm = _make_mock_llm_standardizer()
    agent = StandardizerAgent(
        strategy="llm_required",
        llm_standardizer=mock_llm,
    )
    items, audits = agent.standardize_batch([raw_item])

    assert len(items) == 1
    item = items[0]
    StandardizedIntelDTO.model_validate(item)

    # LLM-derived fields
    assert item["canonical_name"] == "LangChain Agent Prompt Injection via Tool Hijack"
    assert item["attack_family"] == "prompt_injection"
    assert item["severity_level"] == "high"
    assert item["source_metadata"]["standardization_strategy"] == "llm_primary"
    assert item["source_metadata"]["llm_model"] == "qwen-max"
    assert item["source_metadata"]["prompt_version"] == "v2.0-llm-primary"
    assert item["extraction_confidence"] == 0.91

    # BOM mentions from LLM
    assert len(item["bom_mentions"]) >= 1
    assert item["bom_mentions"][0]["mentioned_name"] == "langchain"

    # Taxonomy from LLM (validated by RuleValidatorFuser)
    assert len(item["taxonomy_items"]) >= 1
    assert item["taxonomy_items"][0]["taxonomy_code"] == "OWASP-LLM-01"

    # Audit
    audit = audits[0]
    LlmStandardizationAuditDTO.model_validate(audit)
    assert audit["strategy_executed"] == "llm_primary"
    assert audit["llm_confidence"] == 0.91
    assert audit["evidence_span_count"] >= 3
    assert audit["field_confidence_count"] >= 5
    assert audit["fallback_reason"] is None

    # LLM was called
    mock_llm.extract.assert_called_once()


# ===========================================================================
# Test 3: LLM-optional degrades gracefully on failure
# ===========================================================================


def test_llm_optional_degrades_on_failure(tmp_path: Path) -> None:
    raw_item = _make_raw_item(tmpdir=tmp_path)
    mock_llm = _make_failing_llm_standardizer()
    agent = StandardizerAgent(
        strategy="llm_optional",
        llm_standardizer=mock_llm,
    )
    items, audits = agent.standardize_batch([raw_item])

    assert len(items) == 1
    item = items[0]
    StandardizedIntelDTO.model_validate(item)

    # Should be degraded
    assert item["source_metadata"]["standardization_strategy"] == "rules_only_degraded"

    # Audit records the degradation
    audit = audits[0]
    assert audit["strategy_executed"] == "rules_only_degraded"
    assert audit["fallback_reason"] is not None
    assert "LLM service unavailable" in audit["fallback_reason"]


# ===========================================================================
# Test 4: llm_required raises on LLM failure
# ===========================================================================


def test_llm_required_raises_on_llm_failure(tmp_path: Path) -> None:
    raw_item = _make_raw_item(tmpdir=tmp_path)
    mock_llm = _make_failing_llm_standardizer()
    agent = StandardizerAgent(
        strategy="llm_required",
        llm_standardizer=mock_llm,
    )
    try:
        agent.standardize_batch([raw_item])
        assert False, "Expected RuntimeError from llm_required + LLM failure"
    except RuntimeError as exc:
        assert "LLM service unavailable" in str(exc)


# ===========================================================================
# Test 5: RuleValidatorFuser standalone
# ===========================================================================


def test_rule_validator_fixes_invalid_taxonomy() -> None:
    fuser = RuleValidatorFuser()
    llm_output = {
        "canonical_name": "Test Attack",
        "attack_family": "prompt_injection",
        "severity_level": "high",
        "summary": "A test attack",
        "description": "Detailed description of test attack",
        "taxonomy_items": [
            {
                "taxonomy_type": "OWASP_LLM",
                "taxonomy_code": "OWASP-LLM-01",
                "taxonomy_name": "Prompt Injection",
                "confidence_score": 0.9,
                "is_primary": False,
            },
            {
                "taxonomy_type": "INVALID_TYPE",
                "taxonomy_code": "XX-99",
                "taxonomy_name": "Fake",
                "confidence_score": 0.5,
                "is_primary": True,
            },
        ],
        "cvss_hint": {
            "base_score": 8.0,
            "severity_label": "High",
            "cvss_version": "3.1",
            "score_origin": "estimated",
        },
        "bom_mentions": [],
    }
    result = fuser.validate_and_fuse(llm_output)

    # Invalid taxonomy type should be dropped, findings should record it
    assert any("unrecognized" in f for f in result["validation_findings"])
    # Remaining taxonomy should auto-promote to primary
    valid_items = result["taxonomy_items"]
    assert len(valid_items) == 1
    assert valid_items[0]["is_primary"] is True


def test_rule_validator_detects_severity_cvss_mismatch() -> None:
    fuser = RuleValidatorFuser()
    llm_output = {
        "canonical_name": "Low sev high score",
        "attack_family": "data_leakage",
        "severity_level": "low",
        "summary": "Mismatch test",
        "description": "Testing CVSS/severity mismatch",
        "taxonomy_items": [
            {
                "taxonomy_type": "CWE",
                "taxonomy_code": "CWE-200",
                "taxonomy_name": "Information Exposure",
                "confidence_score": 0.7,
                "is_primary": True,
            }
        ],
        "cvss_hint": {
            "base_score": 9.0,
            "severity_label": "Critical",
            "cvss_version": "3.1",
            "score_origin": "estimated",
        },
        "bom_mentions": [],
    }
    result = fuser.validate_and_fuse(llm_output)
    assert "severity_cvss_mismatch_low_vs_high_score" in result["conflict_flags"]


def test_rule_validator_deduplicates_bom_mentions() -> None:
    fuser = RuleValidatorFuser()
    llm_output = {
        "canonical_name": "Dup BOM",
        "attack_family": "supply_chain",
        "severity_level": "medium",
        "summary": "Dup test",
        "description": "Testing BOM dedup",
        "taxonomy_items": [
            {
                "taxonomy_type": "OWASP_LLM",
                "taxonomy_code": "OWASP-LLM-05",
                "taxonomy_name": "Supply Chain Vulnerabilities",
                "confidence_score": 0.8,
                "is_primary": True,
            }
        ],
        "cvss_hint": None,
        "bom_mentions": [
            {"mentioned_name": "langchain", "confidence_score": 0.9},
            {"mentioned_name": "LangChain", "confidence_score": 0.7},
        ],
    }
    result = fuser.validate_and_fuse(llm_output)
    assert len(result["bom_mentions"]) == 1
    assert any("duplicate" in f.lower() for f in result["validation_findings"])


def test_rule_validator_fuses_unknown_fields() -> None:
    fuser = RuleValidatorFuser()
    llm_output = {
        "canonical_name": "unknown",
        "attack_family": "unknown",
        "severity_level": "medium",
        "summary": "Some summary from LLM",
        "description": "Some description",
        "taxonomy_items": [],
        "cvss_hint": None,
        "bom_mentions": [],
    }
    rule_fallback = {
        "canonical_name": "NVD Intelligence for prompt injection",
        "attack_family": "prompt_injection",
        "summary": "Rule summary",
        "description": "Rule description",
    }
    conservative = fuser.validate_and_fuse(llm_output, rule_fallback=rule_fallback)
    assert conservative["canonical_name"] == "unknown"
    assert conservative["attack_family"] == "unknown"
    result = fuser.validate_and_fuse(
        llm_output, rule_fallback=rule_fallback, allow_field_fusion=True
    )

    # Unknown fields are fused only with explicit opt-in.
    assert result["canonical_name"] == "NVD Intelligence for prompt injection"
    assert result["attack_family"] == "prompt_injection"
    # summary was NOT unknown, so LLM value should be kept
    assert result["summary"] == "Some summary from LLM"
    assert any("rule_fallback_substituted" in t for t in result["normalization_trace"])


# ===========================================================================
# Test 6: DTO shape validation
# ===========================================================================


def test_new_dtos_validate_correctly() -> None:
    evidence = LlmExtractionEvidenceDTO(
        field_name="canonical_name",
        evidence_text="langchain prompt injection",
    )
    assert evidence.field_name == "canonical_name"

    confidence = LlmFieldConfidenceDTO(
        field_name="attack_family",
        confidence=0.88,
        reason="Explicit mention in text",
    )
    assert confidence.confidence == 0.88

    decision = LLMStandardizationDecisionDTO(
        canonical_name="Test Attack",
        attack_family="prompt_injection",
        severity_level="high",
        summary="Test summary",
        description="Test description",
        extraction_reason="Test reason",
        llm_confidence=0.85,
    )
    assert decision.llm_confidence == 0.85


# ===========================================================================
# Test 7: Field confidence from LLM flows through
# ===========================================================================


def test_llm_field_confidences_flow_to_output(tmp_path: Path) -> None:
    raw_item = _make_raw_item(tmpdir=tmp_path)
    mock_llm = _make_mock_llm_standardizer()
    agent = StandardizerAgent(
        strategy="llm_required",
        llm_standardizer=mock_llm,
    )
    items, _ = agent.standardize_batch([raw_item])
    item = items[0]

    # Field confidence should come from LLM per-field results
    fc = item["field_confidence"]
    assert "canonical_name" in fc
    assert "attack_family" in fc
    assert "severity_level" in fc
    assert fc["canonical_name"] == 0.93
    assert fc["bom_mentions"] == 0.92


# ===========================================================================
# Test 8: Batch with multiple items
# ===========================================================================


def test_batch_standardization_multiple_items(tmp_path: Path) -> None:
    raw1 = _make_raw_item(tmpdir=tmp_path, source_name="nvd")
    # Second item with different payload
    payload2 = json.dumps({"text": "agent hijack discussion on reddit"})
    p2 = tmp_path / "payload2.json"
    p2.write_text(payload2, encoding="utf-8")
    raw2 = {
        **raw1,
        "query_run_id": "qr_test_002",
        "source_name": "reddit",
        "title": "Agent hijack via tool misuse",
        "summary": "Discussion about agent hijack techniques",
        "artifact_ref": str(p2),
        "payload_uri": str(p2),
        "content_hash": "b" * 64,
    }

    agent = StandardizerAgent(strategy="rules_only")
    items, audits = agent.standardize_batch([raw1, raw2])

    assert len(items) == 2
    assert len(audits) == 2
    assert items[0]["source_metadata"]["source_name"] == "nvd"
    assert items[1]["source_metadata"]["source_name"] == "reddit"


# ===========================================================================
# Test 9: rules_only_degraded strategy is allowed
# ===========================================================================


def test_rules_only_degraded_strategy_accepted(tmp_path: Path) -> None:
    raw_item = _make_raw_item(tmpdir=tmp_path)
    agent = StandardizerAgent(strategy="rules_only_degraded")
    items, audits = agent.standardize_batch([raw_item])

    assert len(items) == 1
    assert audits[0]["strategy_requested"] == "rules_only_degraded"


# ===========================================================================
# Test 10: Node-level integration — parse_and_standardize_node
# ===========================================================================


def test_parse_and_standardize_node_returns_audits(tmp_path: Path) -> None:
    """Verify the orchestrator node correctly handles the new return format."""
    parse_and_standardize_node = import_module(
        "agents.intel_agents.orchestrator.nodes"
    ).parse_and_standardize_node

    raw_item = _make_raw_item(tmpdir=tmp_path)
    state = {
        "run_id": "run_test",
        "trace_id": "trace_test",
        "run_status": "running",
        "runtime_context": {
            "standardization_strategy": "rules_only",
            "llm_model": "qwen-max",
            "llm_temperature": 0.0,
            "validate_llm_online": False,
        },
        "raw_items": [raw_item],
        "stored_raw_records": [{"query_run_id": "qr_test_001", "raw_id": "raw_001"}],
    }
    patch = parse_and_standardize_node(state)

    assert "standardized_items" in patch
    assert "llm_standardization_audits" in patch
    assert len(patch["standardized_items"]) == 1
    assert len(patch["llm_standardization_audits"]) == 1
    # Node result present
    assert any(
        nr["node_name"] == "parse_and_standardize"
        for nr in patch.get("node_results", [])
    )


# ===========================================================================
# Test 11: Integration — Phase 2 → Phase 3 pipeline (crew → ingest → standardize)
# ===========================================================================


def test_phase3_standardizer_produces_rich_structured_intel(tmp_path: Path) -> None:
    plans = [
        SourceExecutionPlanDTO(
            source_name="github_advisories",
            source_type="code",
            priority=1.0,
            queries=["langchain prompt injection"],
            query_intent="broad_recall",
            query_provenance="test",
            rewrite_reason=None,
            max_results=5,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python")
    ]

    collected = SourceCollectionCrew().collect(
        plans,
        trace_id="trace_phase3_test",
        run_mode="bootstrap",
        reflection_round=0,
        runtime_mode="stub",
        retry_attempts=2,
        request_timeout_seconds=5.0,
        artifact_store_dir=str(tmp_path / "artifacts"),
        source_cursors={},
    )
    stored, _ = RawIngestFlow(str(tmp_path / "manifests")).ingest(
        collected["raw_items"],
        run_id="run_phase3_test",
        trace_id="trace_phase3_test",
    )

    items, audits = StandardizerAgent(strategy="rules_only").standardize_batch(
        collected["raw_items"], stored
    )

    assert len(items) == 1
    item = items[0]
    assert item["attack_code"].startswith("ATTACK-")
    assert item["taxonomy_items"]
    assert item["cvss_hint"] is not None
    assert item["stix_payload"]["type"] == "attack-pattern"
    assert item["evidence_refs"]
    assert item["extraction_reason"]
    assert item["bom_mentions"]
    assert item["field_confidence"]
    assert "validation_findings" in item

    # Audit present
    assert len(audits) == 1
    LlmStandardizationAuditDTO.model_validate(audits[0])


# ===========================================================================
# Test 12: LLM-optional path with mock enhancer (integration)
# ===========================================================================


def test_llm_optional_with_enhancer_produces_enriched_output(tmp_path: Path) -> None:
    """LLM-optional with a working mock produces LLM-primary output."""
    plans = [
        SourceExecutionPlanDTO(
            source_name="github_advisories",
            source_type="code",
            priority=1.0,
            queries=["langchain prompt injection"],
            query_intent="broad_recall",
            query_provenance="test",
            rewrite_reason=None,
            max_results=5,
            fetch_mode="bootstrap",
            time_window_days=7,
        ).model_dump(mode="python")
    ]
    collected = SourceCollectionCrew().collect(
        plans,
        trace_id="trace_phase3_llm",
        run_mode="bootstrap",
        reflection_round=0,
        runtime_mode="stub",
        retry_attempts=2,
        request_timeout_seconds=5.0,
        artifact_store_dir=str(tmp_path / "artifacts"),
        source_cursors={},
    )
    stored, _ = RawIngestFlow(str(tmp_path / "manifests")).ingest(
        collected["raw_items"],
        run_id="run_phase3_llm",
        trace_id="trace_phase3_llm",
    )

    mock_llm = _make_mock_llm_standardizer()
    items, audits = StandardizerAgent(
        strategy="llm_optional",
        llm_standardizer=mock_llm,
    ).standardize_batch(collected["raw_items"], stored)

    item = items[0]
    assert item["canonical_name"] == "LangChain Agent Prompt Injection via Tool Hijack"
    assert item["severity_level"] == "high"
    assert item["source_metadata"]["standardization_strategy"] == "llm_primary"
    assert item["extraction_confidence"] == 0.91
    assert item["field_confidence"]

    # Audit
    audit = audits[0]
    assert audit["strategy_executed"] == "llm_primary"
    assert audit["llm_confidence"] == 0.91


# ===========================================================================
# Test 13: Full runtime integration
# ===========================================================================


def test_phase3_runtime_outputs_standardized_attack_objects() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run()

    assert result["run_status"] == "succeeded"
    assert result["standardized_items"]
    first = result["standardized_items"][0]
    assert first["attack_family"]
    assert "taxonomy_items" in first
    assert "stix_payload" in first
    assert "evidence_refs" in first
    assert first["artifact_ref"]
    # New: audits in state
    assert "llm_standardization_audits" in result
    assert len(result["llm_standardization_audits"]) > 0
