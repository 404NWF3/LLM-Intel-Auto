from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = REPO_ROOT / "backend" / "agents"


def _bootstrap_imports() -> None:
    os.chdir(REPO_ROOT)
    for path in (str(AGENTS_ROOT), str(REPO_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


_bootstrap_imports()

from saads_wp12.config import get_config  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="End-to-end runner for backend/agents/saads_wp12.",
    )
    parser.add_argument(
        "--mode",
        choices=("single", "batch", "list"),
        default="single",
        help="single: run one item; batch: process feed items once; list: inspect feed references.",
    )
    parser.add_argument(
        "--feed-source",
        choices=("mock", "local_json", "db"),
        default="mock",
        help="Feed provider used by saads_wp12.",
    )
    parser.add_argument(
        "--llm-mode",
        choices=("rule", "auto", "llm"),
        default="rule",
        help="WP12_LLM_MODE override for the run.",
    )
    parser.add_argument(
        "--attack-id",
        default="",
        help="Attack identifier to run in single mode. Defaults to the first available item.",
    )
    parser.add_argument(
        "--tenant-id",
        default="local-dev",
        help="tenant_id injected into the graph state for single mode.",
    )
    parser.add_argument(
        "--scenario-id",
        default="demo-scenario",
        help="scenario_id injected into the graph state for single mode.",
    )
    parser.add_argument(
        "--local-feed-root",
        default="",
        help="Override WP12_LOCAL_FEED_ROOT when feed-source=local_json.",
    )
    parser.add_argument(
        "--main-backend-path",
        default="",
        help="Override SAADS_MAIN_BACKEND_PATH when feed-source=db.",
    )
    parser.add_argument(
        "--min-cvss",
        type=float,
        default=None,
        help="Optional WP12_DB_FEED_MIN_CVSS override.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional WP12_DB_FEED_LIMIT override.",
    )
    parser.add_argument(
        "--taxonomy-codes",
        default="",
        help="Comma-separated WP12_DB_FEED_TAXONOMY_CODES override.",
    )
    parser.add_argument(
        "--process-limit",
        type=int,
        default=None,
        help="Optional WP12_PROCESS_LIMIT override for batch mode.",
    )
    parser.add_argument(
        "--registry-path",
        default="",
        help="Optional WP12_DEDUP_REGISTRY_PATH override for batch mode.",
    )
    parser.add_argument(
        "--reset-registry",
        action="store_true",
        help="Delete the configured dedup registry before batch mode starts.",
    )
    parser.add_argument(
        "--list-limit",
        type=int,
        default=20,
        help="Maximum items to show for --mode list.",
    )
    parser.add_argument(
        "--print-plan-head",
        type=int,
        default=0,
        help="Print the first N lines of the generated markdown plan in single mode.",
    )
    return parser


def _set_env_if_present(name: str, value: str | None) -> None:
    if value is None:
        return
    stripped = value.strip()
    if stripped:
        os.environ[name] = stripped


def _apply_env_overrides(args: argparse.Namespace) -> None:
    os.environ["WP12_FEED_SOURCE"] = args.feed_source
    os.environ["WP12_LLM_MODE"] = args.llm_mode

    if args.min_cvss is not None:
        os.environ["WP12_DB_FEED_MIN_CVSS"] = str(args.min_cvss)
    if args.limit is not None:
        os.environ["WP12_DB_FEED_LIMIT"] = str(args.limit)
    if args.process_limit is not None:
        os.environ["WP12_PROCESS_LIMIT"] = str(args.process_limit)

    _set_env_if_present("WP12_DB_FEED_TAXONOMY_CODES", args.taxonomy_codes)
    _set_env_if_present("WP12_DEDUP_REGISTRY_PATH", args.registry_path)
    _set_env_if_present("WP12_LOCAL_FEED_ROOT", args.local_feed_root)
    _set_env_if_present("SAADS_MAIN_BACKEND_PATH", args.main_backend_path)

    get_config.cache_clear()


def _resolve_registry_path() -> Path:
    configured = os.getenv("WP12_DEDUP_REGISTRY_PATH", "").strip()
    if configured:
        return Path(configured)
    return REPO_ROOT / "artifacts" / "processed_attack_ids.json"


def _assert_registry_reset_is_safe(path: Path) -> None:
    resolved = path.resolve()
    repo_artifacts = (REPO_ROOT / "artifacts").resolve()
    if repo_artifacts in resolved.parents or resolved == repo_artifacts:
        return
    raise ValueError(
        f"Refusing to delete registry outside repo artifacts directory: {resolved}"
    )


def _bool_flag(value: Any) -> bool:
    return bool(value)


def _build_preflight_summary(config: Any) -> dict[str, Any]:
    return {
        "repo_root": str(REPO_ROOT),
        "feed_source": config.feed_source,
        "llm_mode": config.llm_mode,
        "llm_enabled": _bool_flag(config.llm_enabled),
        "openai_api_key_present": _bool_flag(config.openai_api_key),
        "local_feed_root": config.local_feed_root,
        "saads_main_backend_path": config.saads_main_backend_path,
        "db_feed_min_cvss": config.db_feed_min_cvss,
        "db_feed_limit": config.db_feed_limit,
        "db_feed_taxonomy_codes": list(config.db_feed_taxonomy_codes),
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _load_provider():
    from saads_wp12.data.feed_provider import get_attack_feed_provider

    return get_attack_feed_provider()


def _load_graph():
    from saads_wp12.agent import graph

    return graph


def _list_feed(args: argparse.Namespace) -> dict[str, Any]:
    provider = _load_provider()
    attack_refs = provider.list_attack_feed_refs()
    attack_refs = attack_refs[: max(args.list_limit, 0)]
    return {
        "mode": "list",
        "count": len(attack_refs),
        "items": [
            {
                "attack_id": attack_id,
                "attack_code": attack_code,
            }
            for attack_id, attack_code in attack_refs
        ],
    }


def _resolve_single_attack_id(requested_attack_id: str) -> tuple[str, dict[str, Any]]:
    provider = _load_provider()
    selected_item = provider.get_attack_feed_item(requested_attack_id or None)
    return selected_item.attack_id, selected_item.to_dict()


def _read_plan_head(plan_path: str, line_count: int) -> list[str]:
    if line_count <= 0:
        return []
    path = Path(plan_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[:line_count]


def _run_single(args: argparse.Namespace) -> dict[str, Any]:
    graph = _load_graph()
    attack_id, intel_raw = _resolve_single_attack_id(args.attack_id)
    initial_state = {
        "attack_id": attack_id,
        "intel_raw": intel_raw,
        "tenant_id": args.tenant_id,
        "scenario_id": args.scenario_id,
    }
    result = graph.invoke(initial_state)

    test_package = result.get("test_package", {})
    execution_assessment = result.get("execution_assessment", {})
    package_validation = result.get("package_validation", {})
    threat_understanding = result.get("threat_understanding", {})
    summary = {
        "mode": "single",
        "run_id": result.get("run_id", ""),
        "attack_id": result.get("attack_id", attack_id),
        "attack_code": intel_raw.get("attack_code", ""),
        "attack_family": result.get("attack_family", ""),
        "supported_family": result.get("supported_family", ""),
        "target_surface": result.get("target_surface", ""),
        "package_kind": test_package.get("package_kind"),
        "generation_mode": test_package.get("generation_mode"),
        "generator_name": (test_package.get("metadata") or {}).get("generator_name"),
        "execution_eligibility": execution_assessment.get("execution_eligibility"),
        "test_readiness": execution_assessment.get("test_readiness"),
        "plan_readiness": (result.get("plan_readiness") or {}).get("overall_readiness"),
        "verdict": result.get("verdict"),
        "env_status": result.get("env_status"),
        "package_valid": package_validation.get("valid"),
        "validation_errors": package_validation.get("validation_errors", []),
        "risk_flags": result.get("risk_flags", []),
        "known_gaps": (result.get("uncertainty_report") or {}).get("known_gaps", []),
        "threat_summary": threat_understanding.get("threat_summary", ""),
        "persistence_path": result.get("persistence_path", ""),
        "raw_state_path": result.get("raw_state_path", ""),
        "presentation_state_path": result.get("presentation_state_path", ""),
        "plan_path": result.get("plan_path", ""),
    }
    if args.print_plan_head > 0 and summary["plan_path"]:
        summary["plan_head"] = _read_plan_head(summary["plan_path"], args.print_plan_head)
    return summary


def _run_batch(args: argparse.Namespace) -> dict[str, Any]:
    if args.reset_registry:
        registry_path = _resolve_registry_path()
        _assert_registry_reset_is_safe(registry_path)
        if registry_path.exists():
            registry_path.unlink()

    from saads_wp12.run_feed_once import run_feed_once

    result = run_feed_once()
    result["mode"] = "batch"
    return result


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _apply_env_overrides(args)

    config = get_config()
    payload: dict[str, Any] = {
        "preflight": _build_preflight_summary(config),
    }

    if args.mode == "list":
        payload["result"] = _list_feed(args)
        _print_json(payload)
        return

    if args.mode == "batch":
        payload["result"] = _run_batch(args)
        _print_json(payload)
        return

    payload["result"] = _run_single(args)
    _print_json(payload)


if __name__ == "__main__":
    main()
