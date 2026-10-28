"""Subprocess bridge; loads only the bundled agent and the platform's credentials."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "red_team/runtime"
sys.path.insert(0, str(RUNTIME))


def watch_parent():
    parent = int(os.environ.get("RED_TEAM_PARENT_PID", os.getppid()))
    while True:
        time.sleep(3)
        if os.getppid() != parent:
            os.killpg(os.getpgrp(), signal.SIGTERM)
            return


def main():
    folder = Path(sys.argv[1]).resolve()
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    config = job["config"]
    threading.Thread(target=watch_parent, daemon=True).start()
    graph_root = (
        Path(os.environ.get("RED_TEAM_GRAPH_ROOT") or RUNTIME).expanduser().resolve()
    )
    print(f"Starting {job['kind']} · {job['run_id']}", flush=True)
    if job["kind"] == "graph":
        from graph_builder import build

        return asyncio.run(build(folder))
    if job["kind"] == "case":
        from saads_attack_agent.__main__ import main as run_case
        from saads_attack_agent.agent import AttackCaseAgent, ClaudeAgentBackend
        from saads_attack_agent.security_graph import SecurityGraph

        async def generate(request):
            print("Loading GraphRAG and recognizing attack intent…", flush=True)
            graph = SecurityGraph.load(graph_root)
            return await AttackCaseAgent(
                ClaudeAgentBackend(project_root=RUNTIME, graph=graph)
            ).generate(request)

        return run_case(
            [config["request"], "--output-root", str(folder / "results")],
            generate=generate,
        )

    import yaml
    from saads_grill_agent import __main__ as cli

    # Keep the trusted bundled Skills root, but allow a separately configured graph index.
    original_resolve = cli.resolve_graph_runtime
    cli.resolve_graph_runtime = lambda *, root, use_graphrag: original_resolve(
        root=graph_root, use_graphrag=use_graphrag
    )
    if "--resume" in sys.argv:
        checkpoint_dir = sys.argv[sys.argv.index("--resume") + 1]
        caps = job["resume_caps"]
        return cli.main(
            [
                "resume",
                checkpoint_dir,
                "--max-agent-calls",
                str(caps["max_agent_calls"]),
                "--max-cost-usd",
                str(caps["max_cost_usd"]),
            ]
        )
    runtime_config = {
        "target_repo": config["target_repo"],
        "authorization_ref": config["authorization_ref"],
        "goal": config["goal"],
        "output_root": str(folder / "results"),
        "max_rounds_per_hypothesis": config["max_rounds"],
        "max_agent_calls": config["max_agent_calls"],
        "max_cost_usd": config["max_cost_usd"],
        "use_graphrag": config["use_graphrag"],
        "scope_excludes": [
            "data/**",
            "frontend/node_modules/**",
            "frontend/.next/**",
            "backend/red_team/runtime/.venv/**",
        ],
        "sdk": {"team_max_turns": 30, "judge_max_turns": 20},
    }
    config_path = folder / "request.yaml"
    config_path.write_text(
        yaml.safe_dump(runtime_config, allow_unicode=True), encoding="utf-8"
    )
    return cli.main(["start", "--config", str(config_path)])


if __name__ == "__main__":
    raise SystemExit(main())
