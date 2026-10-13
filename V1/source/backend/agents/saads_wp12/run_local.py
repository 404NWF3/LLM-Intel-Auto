from __future__ import annotations

import json

from backend.agents.saads_wp12.agent import graph
from backend.agents.saads_wp12.config import get_config


def main() -> None:
    config = get_config()
    initial_state = {
        "tenant_id": "local-dev",
        "scenario_id": "demo-scenario",
    }
    if config.feed_source != "db":
        initial_state["attack_id"] = "atk-001"
    result = graph.invoke(initial_state)
    test_package = result.get("test_package", {})
    execution_assessment = result.get("execution_assessment", {})
    summary = {
        "run_id": result["run_id"],
        "attack_id": result["attack_id"],
        "attack_family": result["attack_family"],
        "package_kind": test_package.get("package_kind"),
        "generation_mode": test_package.get("generation_mode"),
        "execution_eligibility": execution_assessment.get("execution_eligibility"),
        "test_readiness": execution_assessment.get("test_readiness"),
        "env_status": result["env_status"],
        "llm_mode": config.llm_mode,
        "verdict": result["verdict"],
        "persistence_path": result["persistence_path"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
