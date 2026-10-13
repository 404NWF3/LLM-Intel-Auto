from __future__ import annotations

from backend.agents.saads_wp12.engines.test_package_generation import get_test_package_generation_engine
from backend.agents.saads_wp12.state import SecurityEvalState


def generate_test_package_subgraph(state: SecurityEvalState) -> dict:
    return get_test_package_generation_engine().run(state)
