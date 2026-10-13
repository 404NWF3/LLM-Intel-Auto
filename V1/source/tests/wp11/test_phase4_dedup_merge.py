"""Tests for Phase 4 -- dedup / merge (rules-only + LLM-primary).

Covers:
    1. Rules-only backward compatibility and tuple return signature
    2. LLM-primary merge / new / review paths
    3. Fusion logic: agreement, conflict, low confidence, BOM delta guard
    4. High-confidence LLM overrides
    5. llm_required failure and llm_optional fallback
    6. Audit DTO validation
    7. Multi-item batch behavior
    8. Dedup adjudicator LLM-awareness
    9. Node integration for llm_dedup_judgments emission
   10. Runtime integration and state defaults
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DedupMergeAgent = import_module(
    "agents.intel_agents.agents.dedup_merge_agent"
).DedupMergeAgent
DedupAdjudicatorAgent = import_module(
    "agents.intel_agents.agents.dedup_adjudicator_agent"
).DedupAdjudicatorAgent
AttackSignatureMemory = import_module(
    "agents.intel_agents.services.attack_signature_memory"
).AttackSignatureMemory
Phase1GraphRuntime = import_module(
    "agents.intel_agents.orchestrator.runtime"
).Phase1GraphRuntime
LlmDedupJudgmentAuditDTO = import_module(
    "agents.intel_agents.schemas.intel"
).LlmDedupJudgmentAuditDTO
RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO
build_initial_state = import_module(
    "agents.intel_agents.orchestrator.state"
).build_initial_state
semantic_dedup_and_merge_node = import_module(
    "agents.intel_agents.orchestrator.nodes"
).semantic_dedup_and_merge_node


def _base_item(
    *,
    raw_id: str,
    attack_code: str,
    summary: str,
    bom: list[str],
    canonical_name: str = "Prompt Injection via Agent Tooling",
    attack_family: str = "prompt_injection",
    taxonomy_code: str = "OWASP-LLM-01",
    taxonomy_name: str = "Prompt Injection",
) -> dict[str, Any]:
    return {
        "raw_id": raw_id,
        "attack_code": attack_code,
        "canonical_name": canonical_name,
        "attack_family": attack_family,
        "severity_level": "high",
        "summary": summary,
        "description": summary + " This attack targets agent runtime prompt handling.",
        "taxonomy_items": [
            {
                "taxonomy_type": "OWASP_LLM",
                "taxonomy_code": taxonomy_code,
                "taxonomy_name": taxonomy_name,
                "confidence_score": 0.9,
                "is_primary": True,
            }
        ],
        "cvss_hint": {
            "base_score": 8.1,
            "severity_label": "High",
            "cvss_version": "3.1",
            "score_origin": "estimated",
            "vector_string": None,
        },
        "bom_mentions": [
            {
                "mentioned_name": name,
                "mentioned_vendor": None,
                "mentioned_version": None,
                "confidence_score": 0.8,
                "reason_code": "name_mention",
            }
            for name in bom
        ],
        "evidence_refs": [f"https://example.com/{raw_id}", f"artifact://{raw_id}"],
        "source_metadata": {"source_name": "github_advisories", "cve_refs": []},
        "confidence_score": 0.8,
    }


def _stable_record_from_item(
    item: dict[str, Any],
    *,
    stable_attack_id: str = "stable-1",
) -> dict[str, Any]:
    agent = DedupMergeAgent()
    candidate = agent._build_candidate(item)
    stable = agent._new_stable_record(candidate, decision="merge")
    stable["stable_attack_id"] = stable_attack_id
    stable["stable_attack_code"] = stable_attack_id
    stable["last_decision"] = "merge"
    return stable


def _llm_judgment(
    *,
    verdict: str,
    action: str,
    confidence: float,
    explanation: str = "semantic evidence supports the judgment",
    risk_notes: list[str] | None = None,
    evidence_quotes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "recommended_action": action,
        "confidence": confidence,
        "explanation": explanation,
        "risk_notes": risk_notes or [],
        "evidence_quotes": evidence_quotes or ["prompt injection in agent tools"],
    }


def _decision_for_raw(result: dict[str, Any], raw_id: str) -> dict[str, Any]:
    return next(
        row
        for row in result["dedup_decisions"]
        if raw_id in row.get("merge_audit_ref", "")
        or raw_id in str(row.get("matched_attack_id", ""))
        or raw_id in str(row)
    )


def _decision_by_index(result: dict[str, Any], index: int) -> dict[str, Any]:
    return result["dedup_decisions"][index]


class FakeMergeJudge:
    PROMPT_VERSION = "v1.0-test"

    def __init__(
        self,
        judgments: list[dict[str, Any]] | None = None,
        *,
        error: str | None = None,
    ) -> None:
        self._judgments = list(judgments or [])
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def validate_connectivity(self) -> None:
        if self.error == "validate_failed":
            raise RuntimeError("validate_failed")

    def judge(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        if self.error and self.error != "validate_failed":
            raise RuntimeError(self.error)
        if not self._judgments:
            raise AssertionError("No fake LLM judgment configured.")
        return self._judgments.pop(0)


def test_phase4_merges_highly_similar_items_rules_only() -> None:
    agent = DedupMergeAgent(strategy="rules_only")
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and system prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    assert llm_audits == []
    assert len(result["dedup_decisions"]) == 2
    assert (
        sum(1 for row in result["dedup_decisions"] if row["decision"] == "merge") == 1
    )
    assert result["dedup_merged_count"] == 1
    assert result["merge_audits"]


def test_phase4_reviews_similar_items_with_bom_delta_rules_only() -> None:
    agent = DedupMergeAgent(strategy="rules_only")
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in orchestration chain.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in orchestration chain.",
            bom=["llamaindex"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    assert llm_audits == []
    review = next(
        row for row in result["dedup_decisions"] if row["decision"] == "review"
    )
    assert review["bom_delta_detected"] is True
    assert review["reasons"]


def test_phase4_vector_memory_semantic_recall(tmp_path: Path) -> None:
    memory = AttackSignatureMemory(base_dir=str(tmp_path / "qdrant"))
    stable = [
        {
            "stable_attack_id": "stable-1",
            "stable_attack_code": "stable-1",
            "canonical_name": "Prompt Injection via Agent Tooling",
            "attack_family": "prompt_injection",
            "summary": "Prompt injection in agent tools enables misuse.",
            "description": "Prompt injection in agent tools enables misuse.",
            "taxonomy_items": [{"taxonomy_code": "OWASP-LLM-01"}],
            "bom_mentions": [{"mentioned_name": "langchain"}],
            "evidence_refs": ["artifact://raw1"],
            "source_coverage": ["github_advisories"],
        }
    ]
    memory.rebuild_index(stable)
    recalled = memory.semantic_recall(
        {
            "canonical_name": "Prompt Injection via Agent Tooling",
            "attack_family": "prompt_injection",
            "summary": "Prompt injection in agent tools enables misuse.",
            "description": "Prompt injection in agent tools enables misuse.",
            "taxonomy_items": [{"taxonomy_code": "OWASP-LLM-01"}],
            "bom_mentions": [{"mentioned_name": "langchain"}],
            "evidence_refs": ["artifact://raw2"],
        },
        top_k=3,
    )
    assert recalled
    assert recalled[0]["stable_attack_id"] == "stable-1"
    memory.close()


def test_phase4_vector_memory_upsert_overwrites_existing_point_without_reembedding(
    tmp_path: Path,
) -> None:
    memory = AttackSignatureMemory(base_dir=str(tmp_path / "qdrant"))
    original = {
        "stable_attack_id": "stable-1",
        "stable_attack_code": "stable-1",
        "canonical_name": "Prompt Injection via Agent Tooling",
        "attack_family": "prompt_injection",
        "source_coverage": ["github_advisories"],
        "dedup_text": "prompt injection via agent tooling",
        "embedding_signature": [1.0] + [0.0] * 31,
    }
    updated = {
        **original,
        "canonical_name": "Updated Prompt Injection Signature",
        "source_coverage": ["mitre_attack"],
        "embedding_signature": [0.0, 1.0] + [0.0] * 30,
    }
    candidate = {
        "embedding_signature": updated["embedding_signature"],
        "dedup_text": updated["dedup_text"],
    }

    with patch(
        "agents.intel_agents.services.attack_signature_memory.generate_embedding",
        side_effect=AssertionError("unexpected re-embedding"),
    ):
        memory.upsert_record(original)
        memory.upsert_record(updated)
        recalled = memory.semantic_recall(candidate, top_k=3)

    assert recalled
    assert recalled[0]["stable_attack_id"] == "stable-1"
    assert recalled[0]["canonical_name"] == "Updated Prompt Injection Signature"
    assert recalled[0]["source_coverage"] == ["mitre_attack"]
    memory.close()


def test_phase4_existing_records_without_signatures_are_normalized() -> None:
    existing = {
        "stable_attack_id": "stable-db-1",
        "stable_attack_code": "stable-db-1",
        "canonical_name": "Prompt Injection via Agent Tooling",
        "attack_family": "prompt_injection",
        "severity_level": "high",
        "summary": "Prompt injection in agent tools enables misuse.",
        "description": "Prompt injection in agent tools enables misuse.",
        "taxonomy_items": [{"taxonomy_code": "OWASP-LLM-01"}],
        "cvss_hint": None,
        "bom_mentions": [{"mentioned_name": "langchain"}],
        "evidence_refs": ["artifact://seed"],
        "source_coverage": ["db_primary"],
        "related_raw_ids": ["raw-seed"],
        "member_attack_codes": ["ATTACK-SEED"],
        "last_decision": "merge",
        "confidence_score": 0.8,
    }
    candidate = _base_item(
        raw_id="raw-new",
        attack_code="ATTACK-NEW",
        summary="Training data inversion leaks memorized examples from a foundation model.",
        bom=["pytorch"],
        canonical_name="Training Data Inversion via Model Leakage",
        attack_family="model_inversion",
        taxonomy_code="OWASP-LLM-06",
        taxonomy_name="Sensitive Information Disclosure",
    )

    result, _ = DedupMergeAgent(strategy="rules_only").dedup_and_merge(
        [candidate],
        existing_records=[existing],
    )

    normalized = next(
        row
        for row in result["stable_attack_records"]
        if row["stable_attack_id"] == "stable-db-1"
    )
    assert normalized["dedup_text"]
    assert normalized["content_hash_signature"]
    assert isinstance(normalized["simhash_signature"], int)
    assert len(normalized["minhash_signature"]) == 16
    assert len(normalized["embedding_signature"]) == 32


def test_phase4_adjudicator_overrides_merge_when_bom_delta_exists() -> None:
    adjudicator = DedupAdjudicatorAgent()
    decision = adjudicator.adjudicate(
        candidate={"attack_code": "ATTACK-1"},
        system_decision={"decision": "merge", "reasons": []},
        top_k_candidates=[{"stable_attack_id": "stable-1", "semantic_score": 0.9}],
        best_signals={
            "rerank_score": 0.92,
            "taxonomy_score": 0.9,
            "bom_score": 0.1,
            "bom_delta_detected": True,
        },
    )
    assert decision["decision"] == "review"


def test_phase4_optional_llm_adjudication_uses_llm_when_available() -> None:
    class FakeLlmAdjudicator:
        def validate_connectivity(self) -> None:
            return None

        def adjudicate(self, payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "final_decision": "merge",
                "matched_attack_id": "stable-llm-1",
                "rationale": ["llm_override=merge_supported"],
                "risk_notes": ["semantic alignment strong"],
            }

    adjudicator = DedupAdjudicatorAgent(
        strategy="llm_optional",
        llm_adjudicator=FakeLlmAdjudicator(),
        validate_online=True,
    )
    decision = adjudicator.adjudicate(
        candidate={"attack_code": "ATTACK-1"},
        system_decision={"decision": "new", "reasons": []},
        top_k_candidates=[{"stable_attack_id": "stable-llm-1", "semantic_score": 0.95}],
        best_signals={
            "rerank_score": 0.91,
            "taxonomy_score": 0.85,
            "bom_score": 0.8,
            "bom_delta_detected": False,
        },
    )
    assert decision["decision"] == "merge"
    assert decision["matched_attack_id"] == "stable-llm-1"
    assert decision["adjudicator_summary"]["llm_review"] is True


def test_phase4_adjudicator_defers_to_high_confidence_llm_merge_judge() -> None:
    adjudicator = DedupAdjudicatorAgent()
    decision = adjudicator.adjudicate(
        candidate={"attack_code": "ATTACK-1"},
        system_decision={
            "decision": "merge",
            "matched_attack_id": "stable-1",
            "reasons": ["fusion=llm_high_confidence_override"],
            "adjudicator_summary": {
                "llm_merge_judge": True,
                "llm_confidence": 0.93,
                "llm_recommended_action": "merge",
            },
        },
        top_k_candidates=[{"stable_attack_id": "stable-1", "semantic_score": 0.88}],
        best_signals={
            "rerank_score": 0.9,
            "taxonomy_score": 0.9,
            "bom_score": 0.9,
            "bom_delta_detected": False,
        },
    )
    assert decision["decision"] == "merge"
    assert "adjudicator_defers=llm_merge_judge_high_confidence" in decision["reasons"]
    assert decision["adjudicator_summary"]["llm_judge_deferred"] is True


def test_phase4_llm_primary_same_attack_merges() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack",
                    action="merge",
                    confidence=0.92,
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    assert _decision_by_index(result, 1)["decision"] == "merge"
    assert len(llm_audits) == 1
    assert llm_audits[0]["strategy_executed"] == "llm_primary"
    assert llm_audits[0]["fused_final_decision"] == "merge"


def test_phase4_llm_primary_different_attack_creates_new() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="different_attack",
                    action="new",
                    confidence=0.95,
                    explanation="the semantics differ despite lexical overlap",
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    decision = _decision_by_index(result, 1)
    assert decision["decision"] == "new"
    assert "fusion=llm_high_confidence_override" in decision["reasons"]
    assert llm_audits[0]["llm_verdict"] == "different_attack"


def test_phase4_llm_primary_same_attack_but_component_delta_reviews() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack_but_component_delta",
                    action="review",
                    confidence=0.9,
                    explanation="same narrative but different framework impact surface",
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in orchestration chain.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in orchestration chain.",
            bom=["llamaindex"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    assert _decision_by_index(result, 1)["decision"] == "review"
    assert llm_audits[0]["llm_recommended_action"] == "review"


def test_phase4_llm_low_confidence_forces_review() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack",
                    action="merge",
                    confidence=0.59,
                    explanation="signals suggest a merge but confidence is low",
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, _ = agent.dedup_and_merge(items)

    decision = _decision_by_index(result, 1)
    assert decision["decision"] == "review"
    assert "fusion=low_llm_confidence_forces_review" in decision["reasons"]


def test_phase4_fusion_conflict_moderate_confidence_forces_review() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="different_attack",
                    action="new",
                    confidence=0.72,
                    explanation="semantic drift is noticeable but not absolute",
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, _ = agent.dedup_and_merge(items)

    decision = _decision_by_index(result, 1)
    assert decision["decision"] == "review"
    assert "fusion=rule_llm_conflict_forces_review" in decision["reasons"]


def test_phase4_fusion_agreement_executes_merge() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack",
                    action="merge",
                    confidence=0.78,
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    assert _decision_by_index(result, 1)["decision"] == "merge"
    assert llm_audits[0]["fusion_agreed"] is True


def test_phase4_bom_delta_blocks_high_confidence_llm_merge() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack",
                    action="merge",
                    confidence=0.97,
                    explanation="the narrative matches strongly",
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in orchestration chain.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in orchestration chain.",
            bom=["llamaindex"],
        ),
    ]

    result, _ = agent.dedup_and_merge(items)

    decision = _decision_by_index(result, 1)
    assert decision["decision"] == "review"
    assert "fusion=bom_delta_blocks_llm_merge" in decision["reasons"]


def test_phase4_high_confidence_llm_override_of_rule_prior_to_merge() -> None:
    stable = _stable_record_from_item(
        _base_item(
            raw_id="seed-1",
            attack_code="ATTACK-SEED",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        )
    )
    candidate = _base_item(
        raw_id="raw-new",
        attack_code="ATTACK-NEW",
        summary="Training data inversion leaks memorized examples from a foundation model.",
        bom=["langchain"],
        canonical_name="Training Data Inversion via Model Leakage",
        attack_family="model_inversion",
        taxonomy_code="OWASP-LLM-06",
        taxonomy_name="Sensitive Information Disclosure",
    )
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack",
                    action="merge",
                    confidence=0.91,
                    explanation="despite weak rules, the judge sees the same attack pattern",
                )
            ]
        ),
    )

    result, _ = agent.dedup_and_merge([candidate], existing_records=[stable])

    decision = _decision_by_index(result, 0)
    assert decision["decision"] == "merge"
    assert "fusion=llm_high_confidence_override" in decision["reasons"]


def test_phase4_llm_required_failure_raises() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(error="llm_failed"),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    with pytest.raises(RuntimeError, match="llm_failed"):
        agent.dedup_and_merge(items)


def test_phase4_llm_optional_failure_falls_back_to_rules() -> None:
    agent = DedupMergeAgent(
        strategy="llm_optional",
        merge_judge=FakeMergeJudge(error="llm_failed"),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items)

    assert _decision_by_index(result, 1)["decision"] == "merge"
    assert len(llm_audits) == 1
    assert llm_audits[0]["strategy_executed"] == "rules_only_fallback"
    assert llm_audits[0]["fallback_reason"] == "llm_failed"


def test_phase4_llm_audit_dto_validation() -> None:
    agent = DedupMergeAgent(
        strategy="llm_required",
        llm_model="qwen-max",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(
                    verdict="same_attack",
                    action="merge",
                    confidence=0.95,
                )
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw1",
            attack_code="ATTACK-1",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw2",
            attack_code="ATTACK-2",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
    ]

    _, llm_audits = agent.dedup_and_merge(items)

    validated = LlmDedupJudgmentAuditDTO.model_validate(llm_audits[0])
    assert validated.candidate_raw_id == "raw2"
    assert validated.candidate_attack_code == "ATTACK-2"
    assert validated.strategy_requested == "llm_required"
    assert validated.strategy_executed == "llm_primary"
    assert validated.llm_model == "qwen-max"
    assert validated.prompt_version == "v1.0-test"
    assert validated.llm_verdict == "same_attack"
    assert validated.llm_recommended_action == "merge"
    assert validated.fused_final_decision == "merge"


def test_phase4_multi_item_batch_with_mixed_decisions() -> None:
    stable = _stable_record_from_item(
        _base_item(
            raw_id="seed-1",
            attack_code="ATTACK-SEED",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        )
    )
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(verdict="same_attack", action="merge", confidence=0.92),
                _llm_judgment(
                    verdict="same_attack_but_component_delta",
                    action="review",
                    confidence=0.9,
                ),
                _llm_judgment(
                    verdict="different_attack",
                    action="new",
                    confidence=0.95,
                ),
            ]
        ),
    )
    items = [
        _base_item(
            raw_id="raw-merge",
            attack_code="ATTACK-MERGE",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw-review",
            attack_code="ATTACK-REVIEW",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["llamaindex"],
        ),
        _base_item(
            raw_id="raw-new",
            attack_code="ATTACK-NEW",
            summary="Training data inversion leaks memorized examples from a foundation model.",
            bom=["pytorch"],
            canonical_name="Training Data Inversion via Model Leakage",
            attack_family="model_inversion",
            taxonomy_code="OWASP-LLM-06",
            taxonomy_name="Sensitive Information Disclosure",
        ),
    ]

    result, llm_audits = agent.dedup_and_merge(items, existing_records=[stable])

    assert [row["decision"] for row in result["dedup_decisions"]] == [
        "merge",
        "review",
        "new",
    ]
    assert len(llm_audits) == 3


def test_phase4_vector_memory_rebuilds_once_and_upserts_final_records() -> None:
    stable = _stable_record_from_item(
        _base_item(
            raw_id="seed-1",
            attack_code="ATTACK-SEED",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        )
    )

    class FakeVectorMemory:
        def __init__(self) -> None:
            self.rebuild_snapshots: list[list[str]] = []
            self.upserted_records: list[dict[str, Any]] = []

        def rebuild_index(self, stable_records: list[dict[str, Any]]) -> None:
            self.rebuild_snapshots.append(
                [str(row.get("stable_attack_id")) for row in stable_records]
            )

        def upsert_record(self, record: dict[str, Any]) -> None:
            self.upserted_records.append(
                {
                    "stable_attack_id": str(record.get("stable_attack_id")),
                    "last_decision": str(record.get("last_decision")),
                    "related_raw_ids": list(record.get("related_raw_ids", [])),
                    "source_coverage": list(record.get("source_coverage", [])),
                }
            )

        def semantic_recall(
            self,
            candidate: dict[str, Any],
            *,
            top_k: int = 5,
        ) -> list[dict[str, Any]]:
            return []

    memory = FakeVectorMemory()
    agent = DedupMergeAgent(
        strategy="llm_required",
        merge_judge=FakeMergeJudge(
            [
                _llm_judgment(verdict="same_attack", action="merge", confidence=0.92),
                _llm_judgment(
                    verdict="same_attack_but_component_delta",
                    action="review",
                    confidence=0.9,
                ),
                _llm_judgment(
                    verdict="different_attack",
                    action="new",
                    confidence=0.95,
                ),
            ]
        ),
        vector_memory=memory,
    )
    items = [
        _base_item(
            raw_id="raw-merge",
            attack_code="ATTACK-MERGE",
            summary="Prompt injection in agent tools enables tool misuse and prompt bypass.",
            bom=["langchain"],
        ),
        _base_item(
            raw_id="raw-review",
            attack_code="ATTACK-REVIEW",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["llamaindex"],
        ),
        _base_item(
            raw_id="raw-new",
            attack_code="ATTACK-NEW",
            summary="Training data inversion leaks memorized examples from a foundation model.",
            bom=["pytorch"],
            canonical_name="Training Data Inversion via Model Leakage",
            attack_family="model_inversion",
            taxonomy_code="OWASP-LLM-06",
            taxonomy_name="Sensitive Information Disclosure",
        ),
    ]

    result, _ = agent.dedup_and_merge(items, existing_records=[stable])

    assert [row["decision"] for row in result["dedup_decisions"]] == [
        "merge",
        "review",
        "new",
    ]
    assert memory.rebuild_snapshots == [[stable["stable_attack_id"]]]
    assert [row["last_decision"] for row in memory.upserted_records] == [
        "merge",
        "review",
        "new",
    ]
    assert memory.upserted_records[0]["stable_attack_id"] == stable["stable_attack_id"]
    assert "raw-merge" in memory.upserted_records[0]["related_raw_ids"]


def test_phase4_semantic_dedup_node_emits_llm_judgments() -> None:
    ctx = RuntimeContextDTO.default_stub()
    payload = ctx.model_dump(mode="python")
    payload["dedup_merge_strategy"] = "llm_optional"
    state = build_initial_state(runtime_context=payload)
    state["standardized_items"] = [
        _base_item(
            raw_id="raw-node",
            attack_code="ATTACK-NODE",
            summary="Prompt injection in agent tools enables tool misuse.",
            bom=["langchain"],
        )
    ]

    class FakeVectorMemory:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeDedupMemoryService:
        def __init__(self, base_dir: str | None = None) -> None:
            self.base_dir = base_dir

        def load_records(self, *, trace_id: str | None = None) -> list[dict[str, Any]]:
            return []

        def save_records(
            self,
            records: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> None:
            return None

        def append_audits(
            self,
            audits: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> None:
            return None

    class FakeDedupMergeAgent:
        last_kwargs: dict[str, Any] | None = None

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            FakeDedupMergeAgent.last_kwargs = kwargs

        def dedup_and_merge(
            self,
            items: list[dict[str, Any]],
            existing_records: list[dict[str, Any]] | None = None,
        ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
            return (
                {
                    "dedup_decisions": [
                        {
                            "decision": "merge",
                            "matched_attack_id": "stable-node-1",
                            "similarity_score": 0.91,
                            "reasons": ["fusion=rule_llm_agree"],
                            "bom_delta_detected": False,
                            "narrative_delta_detected": False,
                            "content_hash_match": False,
                            "simhash_score": 0.84,
                            "minhash_score": 0.81,
                            "embedding_score": 0.9,
                            "rerank_score": 0.93,
                            "taxonomy_overlap_score": 0.9,
                            "cve_overlap_score": 0.0,
                            "bom_overlap_score": 1.0,
                            "matched_candidate_ids": ["stable-node-1"],
                            "merge_audit_ref": "audit-node-1",
                            "adjudicator_summary": {"llm_merge_judge": True},
                        }
                    ],
                    "stable_attack_records": [
                        {
                            "stable_attack_id": "stable-node-1",
                            "stable_attack_code": "stable-node-1",
                            "canonical_name": items[0]["canonical_name"],
                            "attack_family": items[0]["attack_family"],
                            "severity_level": items[0]["severity_level"],
                            "summary": items[0]["summary"],
                            "description": items[0]["description"],
                            "taxonomy_items": items[0]["taxonomy_items"],
                            "cvss_hint": items[0]["cvss_hint"],
                            "bom_mentions": items[0]["bom_mentions"],
                            "evidence_refs": items[0]["evidence_refs"],
                            "source_coverage": ["github_advisories"],
                            "related_raw_ids": [items[0]["raw_id"]],
                            "member_attack_codes": [items[0]["attack_code"]],
                            "last_decision": "merge",
                            "confidence_score": 0.9,
                        }
                    ],
                    "merge_audits": [
                        {
                            "merge_audit_id": "audit-node-1",
                            "stable_attack_id": "stable-node-1",
                            "candidate_raw_id": items[0]["raw_id"],
                            "decision": "merge",
                            "incoming_attack_code": items[0]["attack_code"],
                            "matched_attack_id": "stable-node-1",
                            "similarity_score": 0.91,
                            "reasons": ["fusion=rule_llm_agree"],
                            "bom_delta_detected": False,
                            "narrative_delta_detected": False,
                            "evidence_refs": items[0]["evidence_refs"],
                            "source_coverage": ["github_advisories"],
                            "created_at": "2026-03-16T00:00:00+00:00",
                        }
                    ],
                    "resolved_items": [
                        {
                            **items[0],
                            "dedup_decision": "merge",
                            "merge_audit_ref": "audit-node-1",
                        }
                    ],
                    "dedup_merged_count": 1,
                    "new_attack_count": 0,
                },
                [
                    {
                        "candidate_raw_id": items[0]["raw_id"],
                        "candidate_attack_code": items[0]["attack_code"],
                        "existing_stable_id": "stable-node-1",
                        "strategy_requested": "llm_optional",
                        "strategy_executed": "llm_primary",
                        "llm_model": "qwen-max",
                        "prompt_version": "v1.0-test",
                        "llm_confidence": 0.92,
                        "llm_verdict": "same_attack",
                        "llm_recommended_action": "merge",
                        "llm_explanation": "the candidate matches the stable attack",
                        "fallback_reason": None,
                        "rule_prior_decision": "merge",
                        "fused_final_decision": "merge",
                        "fusion_agreed": True,
                        "overall_similarity_score": 0.91,
                        "bom_delta_detected": False,
                        "invoked_at": "2026-03-16T00:00:00+00:00",
                    }
                ],
            )

    with (
        patch(
            "agents.intel_agents.orchestrator.nodes.AttackSignatureMemory",
            FakeVectorMemory,
        ),
        patch(
            "agents.intel_agents.orchestrator.nodes.DedupMemoryService",
            FakeDedupMemoryService,
        ),
        patch(
            "agents.intel_agents.orchestrator.nodes.DedupMergeAgent",
            FakeDedupMergeAgent,
        ),
    ):
        result = semantic_dedup_and_merge_node(state)

    assert FakeDedupMergeAgent.last_kwargs is not None
    assert FakeDedupMergeAgent.last_kwargs["strategy"] == "llm_optional"
    assert "llm_dedup_judgments" in result
    assert len(result["llm_dedup_judgments"]) == 1
    LlmDedupJudgmentAuditDTO.model_validate(result["llm_dedup_judgments"][0])


def test_phase4_runtime_emits_stable_attack_records_and_audits() -> None:
    runtime = Phase1GraphRuntime()
    result = runtime.invoke_stub_run()

    assert result["run_status"] == "succeeded"
    assert result["dedup_decisions"]
    assert result["stable_attack_records"]
    assert result["merge_audits"]
    first = result["stable_attack_records"][0]
    assert first["source_coverage"]
    assert first["member_attack_codes"]


def test_phase4_runtime_state_contains_llm_dedup_judgments() -> None:
    state = build_initial_state()
    assert "llm_dedup_judgments" in state
    assert state["llm_dedup_judgments"] == []
