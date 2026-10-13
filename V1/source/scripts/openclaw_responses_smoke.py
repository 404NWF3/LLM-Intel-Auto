from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_AGENT_ID = "llm-security-intel"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:18789"


def load_openclaw_config(config_path: Path) -> dict[str, Any]:
    return json.loads(config_path.read_text(encoding="utf-8-sig"))


def derive_gateway_url(config: dict[str, Any]) -> str:
    gateway = config.get("gateway") or {}
    bind = gateway.get("bind") or "loopback"
    port = gateway.get("port") or 18789
    host = "127.0.0.1" if bind in {"loopback", "localhost", "0.0.0.0", "::"} else str(bind)
    return f"http://{host}:{port}"


def resolve_token(config: dict[str, Any]) -> str:
    env_token = os.getenv("OPENCLAW_GATEWAY_TOKEN")
    if env_token:
        return env_token
    gateway = config.get("gateway") or {}
    auth = gateway.get("auth") or {}
    token = auth.get("token")
    if token:
        return str(token)
    raise RuntimeError("No Gateway token found. Set OPENCLAW_GATEWAY_TOKEN or gateway.auth.token.")


def probe_models(client: httpx.Client, gateway_url: str, token: str) -> list[str]:
    response = client.get(
        f"{gateway_url.rstrip('/')}/v1/models",
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(10.0, read=10.0),
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise RuntimeError(f"/v1/models returned unexpected payload: {payload!r}")
    return [str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")]


def extract_output_text(payload: dict[str, Any]) -> str:
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
    return "\n".join(parts).strip()


def complete_response(
    client: httpx.Client,
    *,
    gateway_url: str,
    token: str,
    agent_id: str,
    prompt: str,
) -> dict[str, Any]:
    response = client.post(
        f"{gateway_url.rstrip('/')}/v1/responses",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": agent_id,
        },
        json={
            "model": "openclaw",
            "input": prompt,
        },
        timeout=httpx.Timeout(30.0, read=300.0),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"/v1/responses returned unexpected payload: {payload!r}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test OpenClaw HTTP Responses.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to openclaw.json")
    parser.add_argument("--gateway-url", default=None, help="Override Gateway base URL")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID, help="OpenClaw agent id")
    parser.add_argument(
        "--prompt",
        default="请只回复一行：OPENCLAW_FLOW_OK",
        help="Prompt sent to OpenClaw",
    )
    parser.add_argument(
        "--session-key",
        default=None,
        help="Compatibility flag only. The current smoke test does not force an explicit session key.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    config = load_openclaw_config(config_path)
    gateway_url = args.gateway_url or derive_gateway_url(config) or DEFAULT_GATEWAY_URL
    token = resolve_token(config)

    print(f"config={config_path}")
    print(f"gateway_url={gateway_url}")
    print(f"agent_id={args.agent_id}")
    if args.session_key:
        print("session_key=ignored-by-current-smoke-test")

    with httpx.Client() as client:
        model_ids = probe_models(client, gateway_url, token)
        print("models=", ", ".join(model_ids))
        print("response_start")
        payload = complete_response(
            client,
            gateway_url=gateway_url,
            token=token,
            agent_id=args.agent_id,
            prompt=args.prompt,
        )
        print("response_end")
        print(f"response_id={payload.get('id')}")
        print(f"status={payload.get('status')}")
        print(f"final_text={extract_output_text(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
