from __future__ import annotations

from backend.agents.saads_wp12.engines.threat_understanding import get_threat_understanding_engine
from backend.agents.saads_wp12.state import SecurityEvalState


def understand_threat_subgraph(state: SecurityEvalState) -> dict:
    engine = get_threat_understanding_engine()
    return engine.run(state)
