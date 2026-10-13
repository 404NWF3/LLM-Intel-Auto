from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from agents.intel_agents.orchestrator.runtime import Phase1GraphRuntime
from agents.intel_agents.orchestrator.state import build_initial_state
from agents.intel_agents.schemas.patch import validate_patch
from agents.intel_agents.schemas.runtime import RuntimeContextDTO
from agents.intel_agents.services.stix_graph_service import StixGraphService


def _print(title: str) -> None:
    print(f"\n=== {title} ===")


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
        "candidate_count": 3,
        "invoked_at": "2026-03-22T00:00:00Z",
    }


def check_ai_bom_subgraph_contract(verbose: bool = False) -> None:
    from agents.intel_agents.orchestrator.subgraphs import ai_bom_graph as module

    class DummyBomMapperAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def resolve_batch(
            self,
            items: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            assert trace_id == "trace-ai-bom"
            resolved = [
                {
                    **items[0],
                    "bom_resolutions": [
                        {
                            "mentioned_name": "LangChain",
                            "normalized_alias": "langchain",
                            "resolution_status": "resolved",
                            "selected_component": {
                                "component_code": "CMP-LANGCHAIN",
                                "component_name": "LangChain",
                            },
                            "candidate_components": [],
                            "match_confidence": 0.95,
                            "reason_codes": ["llm_reason:strong_alias_match"],
                        }
                    ],
                }
            ]
            audits = [_audit(raw_id=items[0]["raw_id"], mentioned_name="LangChain")]
            return resolved, audits

    class DummyBomReviewerAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def review_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
            reviewed = []
            for item in items:
                reviewed.append(
                    {
                        **item,
                        "bom_resolutions": [
                            {
                                **item["bom_resolutions"][0],
                                "review": {
                                    "decision": "accept",
                                    "reasons": ["evidence is sufficient"],
                                    "ambiguity_notes": [],
                                    "component_suggestion": item["bom_resolutions"][0][
                                        "selected_component"
                                    ],
                                },
                            }
                        ],
                    }
                )
            return {"standardized_items": reviewed, "bom_queue_count": 0}

    with patch.object(module, "BomMapperAgent", DummyBomMapperAgent), patch.object(
        module, "BomResolutionReviewerAgent", DummyBomReviewerAgent
    ):
        state = {
            "trace_id": "trace-ai-bom",
            "runtime_context": RuntimeContextDTO.default_stub().model_dump(
                mode="python"
            ),
            "standardized_items": [_base_item(attack_code="ATTACK-001", raw_id="raw-1")],
            "llm_bom_resolution_audits": [],
            "bom_queue_count": 0,
        }
        result = module.run_ai_bom_subgraph(state)
        validate_patch(result)
        assert result["bom_queue_count"] == 0
        assert len(result["llm_bom_resolution_audits"]) == 1
        assert result["standardized_items"][0]["bom_resolutions"][0]["review"][
            "decision"
        ] == "accept"
        if verbose:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def check_stix_subgraph_contract(verbose: bool = False) -> None:
    from agents.intel_agents.orchestrator.subgraphs import stix_graph as module

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
                        "local_ref": "report-1",
                        "object_type": "report",
                        "name": "Vendor Advisory",
                        "description": "Primary advisory document.",
                        "confidence": 0.82,
                    },
                    {
                        "local_ref": "ap-1",
                        "object_type": "attack-pattern",
                        "name": "Prompt Injection",
                        "description": "Prompt content hijacks tool routing.",
                        "labels": ["genai"],
                        "is_primary": True,
                        "confidence": 0.94,
                    },
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
            return {
                "decision": "accept",
                "reasoning_summary": "The graph is supported by direct evidence.",
                "finding_codes": [],
            }

    class DummyStixGraphService:
        def build_extraction_payload(self, item: dict[str, Any]) -> dict[str, Any]:
            return {"attack_code": item["attack_code"]}

        def materialize_bundle(
            self,
            *,
            item: dict[str, Any],
            graph_draft: dict[str, Any],
        ) -> dict[str, Any]:
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

    with patch.object(module, "LangChainLlmStixExtractor", DummyExtractor), patch.object(
        module, "LangChainLlmStixReviewer", DummyReviewer
    ), patch.object(module, "StixGraphService", DummyStixGraphService):
        state = {
            "trace_id": "trace-stix",
            "runtime_context": RuntimeContextDTO.default_stub().model_dump(
                mode="python"
            ),
            "standardized_items": [_base_item(attack_code="ATTACK-003", raw_id="raw-3")],
            "stix_bundle_refs": [],
        }
        result = module.run_stix_subgraph(state)
        validate_patch(result)
        assert len(result["stix_bundle_refs"]) == 1
        assert result["standardized_items"][0]["stix_graph_status"] == "published"
        if verbose:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def check_real_stix_materialization(verbose: bool = False) -> None:
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
                    {"source_name": "mitre-attack", "external_id": "T1059"}
                ],
                "kill_chain_phases": [
                    {"kill_chain_name": "mitre-attack", "phase_name": "execution"}
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
    objects = materialized["bundle_payload"]["objects"]
    report = next(obj for obj in objects if obj["type"] == "report")
    attack_pattern = next(obj for obj in objects if obj["type"] == "attack-pattern")
    relationship = next(obj for obj in objects if obj["type"] == "relationship")
    assert attack_pattern["id"] == materialized["primary_attack_pattern_stix_id"]
    assert relationship["target_ref"] == attack_pattern["id"]
    assert attack_pattern["id"] in report["object_refs"]
    assert relationship["id"] in report["object_refs"]
    if verbose:
        print(json.dumps(materialized, indent=2, ensure_ascii=False, default=str))


def check_full_runtime_chain(verbose: bool = False) -> None:
    from agents.intel_agents.orchestrator.subgraphs import ai_bom_graph, stix_graph
    from agents.intel_agents.orchestrator import nodes as nodes_module

    class DummyBomMapperAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def resolve_batch(
            self,
            items: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            resolved_items = []
            audits = []
            for idx, item in enumerate(items):
                resolved_items.append(
                    {
                        **item,
                        "bom_resolutions": [
                            {
                                "mentioned_name": "LangChain",
                                "normalized_alias": "langchain",
                                "resolution_status": "resolved",
                                "selected_component": {
                                    "component_code": "CMP-LANGCHAIN",
                                    "component_name": "LangChain",
                                    "vendor_name": "LangChain",
                                },
                                "candidate_components": [],
                                "match_mode": "alias",
                                "match_confidence": 0.95,
                                "reason_codes": ["llm_reason:strong_alias_match"],
                            }
                        ],
                    }
                )
                audits.append(
                    _audit(raw_id=item["raw_id"], mentioned_name=f"LangChain-{idx}")
                )
            return resolved_items, audits

    class DummyBomReviewerAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def review_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
            reviewed = []
            for item in items:
                reviewed.append(
                    {
                        **item,
                        "bom_resolutions": [
                            {
                                **item["bom_resolutions"][0],
                                "review": {
                                    "decision": "accept",
                                    "reasons": ["evidence is sufficient"],
                                    "ambiguity_notes": [],
                                    "component_suggestion": item["bom_resolutions"][0][
                                        "selected_component"
                                    ],
                                },
                            }
                        ],
                    }
                )
            return {"standardized_items": reviewed, "bom_queue_count": 0}

    class DummyExtractor:
        PROMPT_VERSION = "v1-stix-test"

        def __init__(self, **kwargs: Any) -> None:
            self.last_invocation_meta = {"llm_model": "extractor-test-model"}
            self.model = kwargs.get("model", "test-llm")

        def extract(self, payload: dict[str, Any]) -> dict[str, Any]:
            return {
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
                        "labels": ["genai"],
                        "is_primary": True,
                        "confidence": 0.96,
                    },
                ],
                "relationships": [],
                "graph_confidence": 0.91,
            }

    class DummyReviewer:
        def __init__(self, **kwargs: Any) -> None:
            self.last_invocation_meta = {"llm_model": "reviewer-test-model"}
            self.model = kwargs.get("model", "test-llm")

        def review(self, **kwargs: Any) -> dict[str, Any]:
            return {
                "decision": "accept",
                "reasoning_summary": "The graph is supported by direct evidence.",
                "finding_codes": [],
            }

    class DummyStixGraphService:
        def build_extraction_payload(self, item: dict[str, Any]) -> dict[str, Any]:
            return {"attack_code": item["attack_code"]}

        def materialize_bundle(
            self,
            *,
            item: dict[str, Any],
            graph_draft: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "bundle_stix_id": "bundle--runtime",
                "primary_attack_pattern_stix_id": "attack-pattern--runtime",
                "primary_attack_pattern_payload": {
                    "type": "attack-pattern",
                    "id": "attack-pattern--runtime",
                },
                "graph_confidence": graph_draft["graph_confidence"],
                "bundle_payload": {"type": "bundle", "objects": []},
                "object_rows": [],
                "relationship_rows": [],
            }

        def persist_bundle(self, **kwargs: Any) -> dict[str, Any]:
            item = kwargs["item"]
            return {
                "primary_stix_bundle_id": f"bundle-pk-{item['attack_code']}",
                "primary_stix_object_id": f"object-pk-{item['attack_code']}",
                "stix_graph_status": "published",
                "stix_type": "attack-pattern",
                "stix_payload": {
                    "type": "attack-pattern",
                    "id": f"attack-pattern--{item['attack_code']}",
                },
            }

    context = RuntimeContextDTO.default_stub().model_dump(mode="python")
    context.update(
        {
            "bom_resolution_strategy": "llm_required",
            "stix_strategy": "llm_required",
            "standardization_strategy": "rules_only",
            "dedup_merge_strategy": "rules_only",
            "dedup_adjudication_strategy": "rules_only",
            "planning_strategy": "rules_only",
            "reflection_strategy": "rules_only",
            "coverage_strategy": "rules_only",
        }
    )
    initial_state = build_initial_state(run_mode="bootstrap", runtime_context=context)

    class DummyDedupMemoryService:
        def __init__(self, base_dir: str | None = None) -> None:
            self.base_dir = base_dir

        def load_records(self, *, trace_id: str | None = None) -> list[dict[str, Any]]:
            return []

        def save_records(
            self,
            records: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> dict[str, Any]:
            return {
                "attempted_count": len(records),
                "persisted_count": len(records),
                "failed_count": 0,
                "partial_failure_count": 0,
                "dead_letter_count": 0,
                "dead_letter_path": None,
                "failure_reasons": [],
                "substep_counts": {},
            }

        def append_audits(
            self,
            audits: list[dict[str, Any]],
            *,
            trace_id: str | None = None,
        ) -> dict[str, Any]:
            return {
                "attempted_count": len(audits),
                "persisted_count": len(audits),
                "invalid_candidate_count": 0,
                "missing_candidate_count": 0,
                "failed_count": 0,
                "failure_reasons": [],
            }

    with patch.object(ai_bom_graph, "BomMapperAgent", DummyBomMapperAgent), patch.object(
        ai_bom_graph, "BomResolutionReviewerAgent", DummyBomReviewerAgent
    ), patch.object(stix_graph, "LangChainLlmStixExtractor", DummyExtractor), patch.object(
        stix_graph, "LangChainLlmStixReviewer", DummyReviewer
    ), patch.object(stix_graph, "StixGraphService", DummyStixGraphService), patch.object(
        nodes_module, "DedupMemoryService", DummyDedupMemoryService
    ):
        result = Phase1GraphRuntime().invoke(initial_state)
        assert result["run_status"] == "succeeded"
        assert result["llm_bom_resolution_audits"]
        assert result["stix_bundle_refs"]
        assert any(item.get("bom_resolutions") for item in result["standardized_items"])
        assert any(
            item.get("stix_graph_status") == "published"
            for item in result["standardized_items"]
        )
        if verbose:
            summary = {
                "run_status": result["run_status"],
                "processed_count": result.get("processed_count"),
                "bom_audits": len(result.get("llm_bom_resolution_audits", [])),
                "stix_bundle_refs": result.get("stix_bundle_refs", []),
            }
            print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


def _run_check(name: str, fn: Callable[[bool], None], verbose: bool) -> bool:
    try:
        _print(name)
        fn(verbose)
        print(f"PASS: {name}")
        return True
    except Exception:
        print(f"FAIL: {name}")
        traceback.print_exc()
        return False


def run_validation_suite(*, verbose: bool = False) -> int:
    checks: list[tuple[str, Callable[[bool], None]]] = [
        ("AI BOM subgraph contract", check_ai_bom_subgraph_contract),
        ("STIX subgraph contract", check_stix_subgraph_contract),
        ("Real STIX materialization", check_real_stix_materialization),
        ("Full runtime enrichment chain", check_full_runtime_chain),
    ]
    passed = 0
    for name, fn in checks:
        if _run_check(name, fn, verbose):
            passed += 1
    _print("Summary")
    print(f"Passed {passed}/{len(checks)} checks")
    return 0 if passed == len(checks) else 1


def main() -> None:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    sys.exit(run_validation_suite(verbose=verbose))


if __name__ == "__main__":
    main()
