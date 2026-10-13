from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.agents.saads_wp12.graphs.subgraphs.test_package_generation import generate_test_package_subgraph
from backend.agents.saads_wp12.graphs.subgraphs.threat_understanding import understand_threat_subgraph
from backend.agents.saads_wp12.nodes.intel import ingest_intel, normalize_intel
from backend.agents.saads_wp12.nodes.persistence import finalize_plan_result, persist_plan_artifacts
from backend.agents.saads_wp12.nodes.validation import validate_test_package
from backend.agents.saads_wp12.state import SecurityEvalState


def build_main_graph():
    graph = StateGraph(SecurityEvalState)

    graph.add_node("ingest_intel", ingest_intel)
    graph.add_node("normalize_intel", normalize_intel)
    graph.add_node("understand_threat_subgraph", understand_threat_subgraph)
    graph.add_node("generate_test_package_subgraph", generate_test_package_subgraph)
    graph.add_node("validate_test_package", validate_test_package)
    graph.add_node("finalize_plan_result", finalize_plan_result)
    graph.add_node("persist_plan_artifacts", persist_plan_artifacts)

    graph.add_edge(START, "ingest_intel")
    graph.add_edge("ingest_intel", "normalize_intel")
    graph.add_edge("normalize_intel", "understand_threat_subgraph")
    graph.add_edge("understand_threat_subgraph", "generate_test_package_subgraph")
    graph.add_edge("generate_test_package_subgraph", "validate_test_package")
    graph.add_edge("validate_test_package", "finalize_plan_result")
    graph.add_edge("finalize_plan_result", "persist_plan_artifacts")
    graph.add_edge("persist_plan_artifacts", END)

    return graph.compile()
