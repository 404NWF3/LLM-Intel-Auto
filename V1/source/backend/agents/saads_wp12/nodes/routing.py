from __future__ import annotations

from backend.agents.saads_wp12.state import SecurityEvalState


def route_attack_family(state: SecurityEvalState) -> dict:
    family = state.get("attack_family", "prompt_injection")
    route_map = {
        "prompt_injection": "prompt_generator",
        "long_horizon_dialogue": "dialogue_generator",
        "tool_hijack": "tool_system_generator",
    }
    return {"generation_route": route_map.get(family, "prompt_generator")}
