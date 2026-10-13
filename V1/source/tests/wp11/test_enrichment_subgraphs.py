from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

RuntimeContextDTO = import_module(
    "agents.intel_agents.schemas.runtime"
).RuntimeContextDTO
validate_patch = import_module("agents.intel_agents.schemas.patch").validate_patch
StixGraphService = import_module(
    "agents.intel_agents.services.stix_graph_service"
).StixGraphService
BomResolutionReviewerAgent = import_module(
    "agents.intel_agents.agents.bom_resolution_reviewer_agent"
).BomResolutionReviewerAgent
RuleValidatorFuser = import_module(
    "agents.intel_agents.tools.rule_validator_fuser"
).RuleValidatorFuser


def _base_item(*, attack_code: str, raw_id: str) -> dict[str, Any]:
    return {
        "raw_id": raw_id,
        "attack_code": attack_code,
        "canonical_name": "Prompt Injection Against Agent Tooling",
        "attack_family": "prompt_injection",
        "severity_level": "high",
        "summary": "Prompt input hijacks downstream tool execution.",
        "description": "A crafted prompt redirects the agent to unsafe tool actions.",
        "artifact_ref": "memory://artifact",
        "evidence_refs": ["https://example.com/advisory"],
        "extraction_reason": "Explicit prompt injection narrative in advisory.",
        "source_confidence": 0.9,
        "extraction_confidence": 0.92,
        "taxonomy_items": [],
        "cvss_hint": None,
        "bom_mentions": [],
        "source_metadata": {},
        "field_confidence": {},
        "conflict_flags": [],
        "validation_findings": [],
        "normalization_trace": [],
    }


def _audit(*, raw_id: str, mentioned_name: str) -> dict[str, Any]:
    return {
        "raw_id": raw_id,
        "mention_index": 0,
        "mentioned_name": mentioned_name,
        "strategy_requested": "llm_required",
        "strategy_executed": "llm_primary",
        "llm_model": "test-llm",
        "prompt_version": "v1-test",
        "llm_confidence": 0.91,
        "llm_decision": "accept",
        "llm_reasoning": "Evidence clearly names the affected component.",
        "reasoning_trace": ["Evidence names the component directly."],
        "evidence_quotes": ["The advisory explicitly references LangChain."],
        "candidate_count": 3,
        "invoked_at": "2026-03-22T00:00:00Z",
    }


def test_ai_bom_subgraph_returns_patch_contract(monkeypatch) -> None:
    module = import_module("agents.intel_agents.orchestrator.subgraphs.ai_bom_graph")

    class DummyBomMapperAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def resolve_batch(
            self,
            items: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            assert trace_id == "trace-test"
            resolved = [
                {
                    **items[0],
                    "bom_resolutions": [
                        {
                            "mentioned_name": "LangChain",
                            "normalized_alias": "langchain",
                            "resolution_status": "resolved",
                        }
                    ],
                },
                {
                    **items[1],
                    "bom_resolutions": [
                        {
                            "mentioned_name": "Unknown Stack",
                            "normalized_alias": "unknownstack",
                            "resolution_status": "review_queue",
                        }
                    ],
                },
            ]
            audits = [
                _audit(raw_id=items[0]["raw_id"], mentioned_name="LangChain"),
                _audit(raw_id=items[1]["raw_id"], mentioned_name="Unknown Stack"),
            ]
            return resolved, audits

        def persist_batch(
            self,
            items: list[dict[str, Any]],
            *,
            audits: list[dict[str, Any]] | None = None,
            trace_id: str | None = None,
        ) -> tuple[list[dict[str, Any]], int]:
            assert trace_id == "trace-test"
            assert len(audits or []) == 2
            return items, 1

    monkeypatch.setattr(module, "BomMapperAgent", DummyBomMapperAgent)

    class DummyBomReviewerAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def review_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
            return {
                "standardized_items": [
                    {
                        **items[0],
                        "bom_resolutions": [
                            {
                                **items[0]["bom_resolutions"][0],
                                "review": {
                                    "decision": "accept",
                                    "confidence": 0.93,
                                    "reasons": ["evidence is strong"],
                                    "ambiguity_notes": [],
                                    "review_trace": ["Reviewer confirmed the evidence."],
                                    "component_suggestion": items[0]["bom_resolutions"][0].get(
                                        "selected_component"
                                    ),
                                },
                            }
                        ],
                    },
                    {
                        **items[1],
                        "bom_resolutions": [
                            {
                                **items[1]["bom_resolutions"][0],
                                "review": {
                                    "decision": "review_queue",
                                    "confidence": 0.42,
                                    "reasons": ["evidence is weak"],
                                    "ambiguity_notes": ["candidate overlap remains high"],
                                    "review_trace": ["Reviewer downgraded the result."],
                                    "component_suggestion": None,
                                },
                            }
                        ],
                    },
                ],
                "bom_queue_count": 1,
            }

    monkeypatch.setattr(module, "BomResolutionReviewerAgent", DummyBomReviewerAgent)

    state = {
        "trace_id": "trace-test",
        "runtime_context": RuntimeContextDTO.default_stub().model_dump(mode="python"),
        "standardized_items": [
            _base_item(attack_code="ATTACK-001", raw_id="raw-1"),
            _base_item(attack_code="ATTACK-002", raw_id="raw-2"),
        ],
        "llm_bom_resolution_audits": [],
        "bom_queue_count": 0,
    }

    result = module.run_ai_bom_subgraph(state)

    assert set(result) == {
        "standardized_items",
        "llm_bom_resolution_audits",
        "bom_queue_count",
        "runtime_context",
    }
    assert result["bom_queue_count"] == 1
    assert result["runtime_context"]["pending_queue_summary"]["unresolved_bom"] == 1
    assert len(result["llm_bom_resolution_audits"]) == 2
    validate_patch(result)


def test_bom_resolution_reviewer_uses_llm_critic_decision(monkeypatch) -> None:
    module = import_module("agents.intel_agents.agents.bom_resolution_reviewer_agent")

    class DummyLlmReviewer:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def review(self, payload: dict[str, Any]) -> dict[str, Any]:
            assert "resolution_json" in payload
            return {
                "decision": "review_queue",
                "reasons": ["vendor signal is weak and evidence is ambiguous"],
                "ambiguity_notes": ["candidate overlap remains high"],
                "component_suggestion": None,
            }

    monkeypatch.setattr(module, "LangChainLlmBomReviewer", DummyLlmReviewer)

    reviewer = BomResolutionReviewerAgent(
        strategy="llm_required",
        llm_model="test-llm",
        llm_temperature=0.0,
        llm_runtime_config={},
    )
    checked = reviewer.review_resolution(
        {
            "mentioned_name": "LangChain",
            "mentioned_vendor": "LangChain",
            "normalized_alias": "langchain",
            "resolution_status": "resolved",
            "selected_component": {
                "component_code": "CMP-LANGCHAIN",
                "component_name": "LangChain",
                "vendor_name": "LangChain",
            },
            "candidate_components": [
                {
                    "component_code": "CMP-LANGCHAIN",
                    "component_name": "LangChain",
                    "vendor_name": "LangChain",
                    "match_mode": "alias",
                    "match_score": 0.95,
                    "vendor_score": 1.0,
                    "final_score": 0.95,
                    "aliases": ["langchain"],
                    "reasons": ["alias match"],
                }
            ],
            "match_mode": "alias",
            "match_confidence": 0.95,
            "reason_codes": ["llm_reason:strong_alias_match"],
        },
        attack_context={
            "attack_name": "Prompt Injection",
            "attack_family": "prompt_injection",
            "attack_summary": "Prompt input hijacks tool execution.",
        },
        evidence_text="The advisory references LangChain but does not fully disambiguate the deployment path.",
    )

    assert checked["resolution_status"] == "review_queue"
    assert checked["review"]["decision"] == "review_queue"


def test_stix_subgraph_returns_filtered_patch_and_enriched_items(monkeypatch) -> None:
    module = import_module("agents.intel_agents.orchestrator.subgraphs.stix_graph")

    class DummyExtractor:
        PROMPT_VERSION = "v1-stix-test"

        def __init__(self, **kwargs: Any) -> None:
            self.model = kwargs.get("model", "test-llm")
            self.last_invocation_meta = {"llm_model": "extractor-test-model"}

        def extract(self, payload: dict[str, Any]) -> dict[str, Any]:
            assert payload["attack_code"] == "ATTACK-003"
            return {
                "objects": [
                    {
                        "local_ref": "ap-1",
                        "object_type": "attack-pattern",
                        "name": "Prompt Injection",
                        "description": "Prompt content hijacks tool routing.",
                        "labels": ["genai"],
                        "is_primary": True,
                        "confidence": 0.94,
                    }
                ],
                "relationships": [],
                "graph_confidence": 0.94,
            }

    class DummyReviewer:
        def __init__(self, **kwargs: Any) -> None:
            self.model = kwargs.get("model", "test-llm")
            self.last_invocation_meta = {"llm_model": "reviewer-test-model"}

        def review(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["attack_code"] == "ATTACK-003"
            assert "graph_validation_json" in kwargs
            assert "evidence_text" in kwargs
            return {
                "decision": "accept",
                "confidence": 0.96,
                "reasoning_summary": "The graph is supported by direct evidence.",
                "finding_codes": [],
                "review_trace": ["Reviewer found the graph publishable."],
            }

    class DummyStixGraphService:
        def build_extraction_payload(self, item: dict[str, Any]) -> dict[str, Any]:
            return {
                "attack_code": item["attack_code"],
                "evidence_text": item["description"],
            }

        def validate_graph_draft(
            self,
            *,
            item: dict[str, Any],
            graph_draft: dict[str, Any] | None,
        ) -> dict[str, Any]:
            assert graph_draft is not None
            return {
                "fatal": False,
                "findings": [],
            }

        def materialize_bundle(
            self,
            *,
            item: dict[str, Any],
            graph_draft: dict[str, Any],
            validation: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            assert validation == {"fatal": False, "findings": []}
            return {
                "bundle_stix_id": "bundle--draft",
                "primary_attack_pattern_stix_id": "attack-pattern--draft",
                "primary_attack_pattern_payload": {
                    "type": "attack-pattern",
                    "id": "attack-pattern--draft",
                },
                "graph_confidence": graph_draft["graph_confidence"],
                "bundle_payload": {"type": "bundle", "objects": []},
                "object_rows": [],
                "relationship_rows": [],
            }

        def persist_bundle(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["validation"] == {"fatal": False, "findings": []}
            assert kwargs["runtime_context"]["stix_strategy"] in {
                "disabled",
                "llm_required",
            }
            return {
                "primary_stix_bundle_id": "bundle-pk-1",
                "primary_stix_object_id": "object-pk-1",
                "stix_graph_status": "published",
                "stix_type": "attack-pattern",
                "stix_payload": {
                    "type": "attack-pattern",
                    "id": "attack-pattern--draft",
                },
            }

    monkeypatch.setattr(module, "LangChainLlmStixExtractor", DummyExtractor)
    monkeypatch.setattr(module, "LangChainLlmStixReviewer", DummyReviewer)
    monkeypatch.setattr(module, "StixGraphService", DummyStixGraphService)

    state = {
        "trace_id": "trace-stix",
        "runtime_context": RuntimeContextDTO.default_stub().model_dump(mode="python"),
        "standardized_items": [_base_item(attack_code="ATTACK-003", raw_id="raw-3")],
        "stix_bundle_refs": [],
    }

    result = module.run_stix_subgraph(state)

    assert set(result) == {"standardized_items", "stix_bundle_refs"}
    assert len(result["stix_bundle_refs"]) == 1
    assert result["stix_bundle_refs"][0]["primary_stix_bundle_id"] == "bundle-pk-1"
    assert result["standardized_items"][0]["stix_graph_status"] == "published"
    assert "trace_id" not in result
    validate_patch(result)


def test_stix_graph_service_materialize_bundle_builds_report_refs_and_relationships() -> None:
    service = StixGraphService()
    item = _base_item(attack_code="ATTACK-004", raw_id="raw-4")
    graph_draft = {
        "objects": [
            {
                "local_ref": "report-1",
                "object_type": "report",
                "name": "Vendor Advisory",
                "description": "Primary advisory document.",
                "confidence": 0.82,
            },
            {
                "local_ref": "attack-1",
                "object_type": "attack-pattern",
                "name": "Prompt Injection",
                "description": "Malicious prompts alter agent behavior.",
                "labels": ["genai", "prompt-injection"],
                "external_references": [
                    {
                        "source_name": "mitre-attack",
                        "external_id": "T1059",
                    }
                ],
                "kill_chain_phases": [
                    {
                        "kill_chain_name": "mitre-attack",
                        "phase_name": "execution",
                    }
                ],
                "is_primary": True,
                "confidence": 0.96,
            },
            {
                "local_ref": "coa-1",
                "object_type": "course-of-action",
                "name": "Prompt Sanitization",
                "description": "Filter and constrain unsafe prompts.",
                "confidence": 0.76,
            },
        ],
        "relationships": [
            {
                "source_ref": "coa-1",
                "target_ref": "attack-1",
                "relationship_type": "mitigates",
                "description": "Prompt filtering mitigates the attack.",
                "confidence": 0.79,
            }
        ],
        "graph_confidence": 0.89,
    }

    materialized = service.materialize_bundle(item=item, graph_draft=graph_draft)
    bundle = materialized["bundle_payload"]
    objects = bundle["objects"]

    assert bundle["type"] == "bundle"
    assert materialized["primary_attack_pattern_stix_id"].startswith(
        "attack-pattern--"
    )

    report = next(obj for obj in objects if obj["type"] == "report")
    attack_pattern = next(obj for obj in objects if obj["type"] == "attack-pattern")
    relationship = next(obj for obj in objects if obj["type"] == "relationship")

    assert attack_pattern["id"] == materialized["primary_attack_pattern_stix_id"]
    assert attack_pattern["kill_chain_phases"][0]["phase_name"] == "execution"
    assert relationship["relationship_type"] == "mitigates"
    assert relationship["source_ref"].startswith("course-of-action--")
    assert relationship["target_ref"] == attack_pattern["id"]
    assert attack_pattern["id"] in report["object_refs"]
    assert relationship["id"] in report["object_refs"]


def test_rule_validator_fuser_stays_validator_only_by_default() -> None:
    validated = RuleValidatorFuser().validate_and_fuse(
        {
            "canonical_name": "",
            "attack_family": "prompt_injection",
            "severity_level": "high",
            "summary": "",
            "description": "",
            "taxonomy_items": [],
            "cvss_hint": None,
            "bom_mentions": [],
        },
        rule_fallback={
            "canonical_name": "Rule Derived Name",
            "summary": "Rule Derived Summary",
            "description": "Rule Derived Description",
        },
    )

    assert validated["canonical_name"] == "unknown"
    assert validated["summary"] == "unknown"
    assert validated["description"] == "unknown"
    assert "rule_fallback_substituted" not in " ".join(
        validated["normalization_trace"]
    )


def test_bom_mapper_persist_batch_applies_review_result_before_db_write(
    monkeypatch,
) -> None:
    module = import_module("agents.intel_agents.agents.bom_mapper_agent")
    service_module = import_module(
        "agents.intel_agents.services.component_resolution_service"
    )

    impact_writes: list[dict[str, Any]] = []
    audit_writes: list[dict[str, Any]] = []
    queue_writes: list[dict[str, Any]] = []

    class DummyComponentsRepo:
        def insert_attack_component_mention(self, **kwargs: Any):
            return type("Mention", (), {"mention_id": "mention-1"})()

        def upsert_attack_component_impact(self, **kwargs: Any):
            impact_writes.append(kwargs)
            return type("Impact", (), {"impact_id": "impact-1"})()

    class DummyGovernanceRepo:
        def insert_bom_resolution_audit(self, **kwargs: Any):
            audit_writes.append(kwargs)
            return type("Audit", (), {"audit_id": 1})()

        def enqueue_bom_resolution(self, **kwargs: Any):
            queue_writes.append(kwargs)
            return type("Queue", (), {"queue_id": 7})()

    class DummyAttackRepo:
        def get_attack_by_code(self, attack_code: str):
            assert attack_code == "stable-bom-1"
            return type("Attack", (), {"attack_id": "attack-1"})()

    class DummyUow:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.components = DummyComponentsRepo()
            self.governance = DummyGovernanceRepo()
            self.attacks = DummyAttackRepo()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class DummySeedService:
        def __init__(self, uow: Any) -> None:
            self.uow = uow

        def ensure_seeded(self, trace_id: str | None = None) -> None:
            return None

    monkeypatch.setattr(module, "UnitOfWork", DummyUow)
    monkeypatch.setattr(module, "AiComponentSeedService", DummySeedService)

    agent = module.BomMapperAgent(
        resolution_service=service_module.ComponentResolutionService(),
        strategy="llm_required",
        llm_runtime_config={
            "bom_auto_publish_threshold": 0.85,
            "review_queue_threshold": 0.60,
        },
    )

    item = {
        **_base_item(attack_code="ATTACK-BOM-1", raw_id="raw-bom-1"),
        "bom_mentions": [
            {
                "mentioned_name": "LangChain",
                "mentioned_vendor": "LangChain",
                "mentioned_version": "0.2.x",
                "component_layer": "framework",
                "impact_scope": "direct",
                "dependency_role": "runtime",
                "confidence_score": 0.91,
            }
        ],
        "bom_resolutions": [
            {
                "mentioned_name": "LangChain",
                "mentioned_vendor": "LangChain",
                "mentioned_version": "0.2.x",
                "normalized_alias": "langchain",
                "normalized_vendor": "langchain",
                "normalized_version_constraint": "0.2.x",
                "resolution_status": "resolved",
                "selected_component": {
                    "component_id": "cmp-1",
                    "component_code": "CMP-LANGCHAIN",
                    "component_name": "LangChain",
                    "vendor_name": "LangChain",
                    "match_mode": "alias",
                    "final_score": 0.92,
                },
                "candidate_components": [
                    {
                        "component_id": "cmp-1",
                        "component_code": "CMP-LANGCHAIN",
                        "component_name": "LangChain",
                        "vendor_name": "LangChain",
                        "match_mode": "alias",
                        "match_score": 0.92,
                        "vendor_score": 0.08,
                        "final_score": 0.92,
                        "aliases": ["langchain"],
                        "reasons": ["alias match"],
                    }
                ],
                "match_mode": "alias",
                "match_confidence": 0.92,
                "reason_codes": ["llm_reason:alias_match"],
                "queue_ref": None,
                "review": {
                    "decision": "review_queue",
                    "confidence": 0.41,
                    "reasons": ["reviewer needs manual confirmation"],
                    "ambiguity_notes": ["vendor overlap"],
                    "review_trace": ["Reviewer downgraded the resolution."],
                    "component_suggestion": None,
                },
            }
        ],
        "source_metadata": {"stable_attack_code": "stable-bom-1"},
    }
    audits = [_audit(raw_id="raw-bom-1", mentioned_name="LangChain")]

    persisted_items, queue_count = agent.persist_batch(
        [item],
        audits=audits,
        trace_id="trace-bom-persist",
    )

    assert queue_count == 1
    assert len(impact_writes) == 1
    assert impact_writes[0]["review_status"] == "review_queue"
    assert len(queue_writes) == 1
    assert queue_writes[0]["reason_code"] in {
        "llm_low_confidence",
        "reviewer_rejected",
    }
    assert len(audit_writes) == 1
    assert audit_writes[0]["reasoning_trace"] == [
        "Evidence names the component directly."
    ]
    assert persisted_items[0]["bom_resolutions"][0]["queue_ref"] == "7"


def test_stix_graph_service_validation_rejects_indicator_without_pattern() -> None:
    service = StixGraphService()
    item = _base_item(attack_code="ATTACK-STIX-VAL", raw_id="raw-stix-val")
    graph_draft = {
        "objects": [
            {
                "local_ref": "report-1",
                "object_type": "report",
                "name": "Vendor Advisory",
                "confidence": 0.7,
            },
            {
                "local_ref": "attack-1",
                "object_type": "attack-pattern",
                "name": "Prompt Injection",
                "is_primary": True,
                "confidence": 0.9,
            },
            {
                "local_ref": "indicator-1",
                "object_type": "indicator",
                "name": "IOC",
                "confidence": 0.6,
            },
        ],
        "relationships": [],
        "graph_confidence": 0.7,
    }

    validation = service.validate_graph_draft(item=item, graph_draft=graph_draft)

    assert validation["fatal"] is True
    assert any(
        finding.startswith("indicator_missing_pattern:")
        for finding in validation["findings"]
    )


def test_stix_graph_service_persist_bundle_prefers_stable_attack_code(monkeypatch) -> None:
    module = import_module("agents.intel_agents.services.stix_graph_service")
    looked_up_codes: list[str] = []
    attack_updates: list[dict[str, Any]] = []
    audit_writes: list[dict[str, Any]] = []

    class DummyStixRepo:
        def create_bundle(self, **kwargs: Any):
            return type("Bundle", (), {"bundle_id": "bundle-pk-1"})()

        def create_object(self, **kwargs: Any):
            object_pk = "object-pk-1" if kwargs.get("is_primary") else "object-pk-2"
            return type("Object", (), {"object_pk": object_pk})()

        def insert_object_label(self, **kwargs: Any) -> None:
            return None

        def insert_object_alias(self, **kwargs: Any) -> None:
            return None

        def insert_external_reference(self, **kwargs: Any) -> None:
            return None

        def insert_kill_chain_phase(self, **kwargs: Any) -> None:
            return None

        def insert_relationship_projection(self, **kwargs: Any) -> None:
            return None

        def upsert_attack_binding(self, **kwargs: Any):
            return type("Binding", (), {"binding_id": "binding-1"})()

        def enqueue_review(self, **kwargs: Any):
            return type("Review", (), {"review_id": 1})()

        def insert_extraction_audit(self, **kwargs: Any):
            audit_writes.append(kwargs)
            return type("Audit", (), {"audit_id": 1})()

    class DummyAttackRepo:
        def get_attack_by_code(self, attack_code: str):
            looked_up_codes.append(attack_code)
            if attack_code == "stable-stix-1":
                return type("Attack", (), {"attack_id": "attack-9"})()
            return None

        def update_attack_entry(self, attack_id: str, **updates: Any):
            attack_updates.append({"attack_id": attack_id, **updates})
            return type("Attack", (), {"attack_id": attack_id})()

    class DummyUow:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.stix = DummyStixRepo()
            self.attacks = DummyAttackRepo()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(module, "UnitOfWork", DummyUow)

    service = module.StixGraphService()
    item = {
        **_base_item(attack_code="RAW-ATTACK-CODE", raw_id="raw-stix-1"),
        "source_metadata": {"stable_attack_code": "stable-stix-1"},
    }
    graph_draft = {
        "reasoning_trace": ["Evidence supports a minimal attack-pattern graph."],
        "objects": [
            {
                "local_ref": "report-1",
                "object_type": "report",
                "name": "Vendor Advisory",
                "confidence": 0.8,
            },
            {
                "local_ref": "attack-1",
                "object_type": "attack-pattern",
                "name": "Prompt Injection",
                "is_primary": True,
                "confidence": 0.95,
            },
        ],
        "relationships": [],
        "graph_confidence": 0.93,
    }
    validation = service.validate_graph_draft(item=item, graph_draft=graph_draft)
    materialized = service.materialize_bundle(
        item=item,
        graph_draft=graph_draft,
        validation=validation,
    )

    persisted = service.persist_bundle(
        item=item,
        graph_draft=graph_draft,
        materialized=materialized,
        validation=validation,
        review_decision={
            "decision": "accept",
            "confidence": 0.94,
            "reasoning_summary": "Graph is grounded and publishable.",
            "finding_codes": [],
            "review_trace": ["Reviewer accepted the graph."],
        },
        extractor_model="extractor-test-model",
        reviewer_model="reviewer-test-model",
        prompt_version="v1-test",
        trace_id="trace-stix-persist",
        runtime_context={
            "stix_auto_publish_threshold": 0.85,
            "review_queue_threshold": 0.60,
        },
    )

    assert looked_up_codes == ["stable-stix-1"]
    assert persisted["stix_graph_status"] == "published"
    assert attack_updates[0]["primary_stix_bundle_id"] == "bundle-pk-1"
    assert audit_writes[0]["review_decision"] == "accept"
