from __future__ import annotations

from backend.agents.saads_wp12.graphs.main_graph import build_main_graph

# The deployed WP1-2 agent is the plan-generation mainline:
# intel -> threat understanding -> test package generation -> validation -> 3-layer artifacts.
AGENT_MAINLINE_STEPS = (
    "ingest_intel",
    "normalize_intel",
    "understand_threat_subgraph",
    "generate_test_package_subgraph",
    "validate_test_package",
    "finalize_plan_result",
    "persist_plan_artifacts",
)

graph = build_main_graph()
