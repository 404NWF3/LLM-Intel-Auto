from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import types
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from api.routers import sentinel


def _make_settings(token: str | None = "test-token") -> sentinel.OpenClawSettings:
    return sentinel.OpenClawSettings(
        config_path=Path("dummy-openclaw.json"),
        config_exists=True,
        config_error=None,
        workspace_root=Path("dummy-workspace"),
        workspace_exists=True,
        workspace_source="test",
        agent_id="llm-security-intel",
        agent_configured=True,
        agent_workspace=Path("dummy-workspace"),
        agent_workspace_matches=True,
        gateway_http_url="http://127.0.0.1:18789",
        gateway_responses_url="http://127.0.0.1:18789/v1/responses",
        gateway_ws_url="ws://127.0.0.1:18789",
        gateway_token=token,
        gateway_token_source="test" if token else None,
        hooks_enabled=False,
        hook_mapping_present=False,
    )


def _make_runtime_tmp_dir(name: str) -> Path:
    path = ROOT / ".runtime" / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_run() -> sentinel.SentinelRun:
    return sentinel.SentinelRun(
        run_id="run-123",
        mode="full",
        transport="openclaw",
        status="running",
        started_at=sentinel._now_iso(),
        use_gateway=True,
    )


def test_load_openclaw_settings_prefers_config_token_and_ignores_hooks_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = _make_runtime_tmp_dir("sentinel-gateway-config")
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "gateway": {
                    "bind": "loopback",
                    "port": 18789,
                    "auth": {"token": "config-token"},
                },
                "agents": {
                    "list": [
                        {
                            "id": "llm-security-intel",
                            "workspace": str(tmp_path / "workspace-llm-security-intel"),
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_HOOKS_TOKEN", "hooks-token")

    settings = sentinel._load_openclaw_settings()

    assert settings.gateway_token == "config-token"
    assert settings.gateway_token_source == "config:gateway.auth.token"


def test_load_openclaw_settings_does_not_fallback_to_hooks_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = _make_runtime_tmp_dir("sentinel-gateway-no-hooks-fallback")
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "gateway": {"bind": "loopback", "port": 18789, "auth": {}},
                "agents": {
                    "list": [
                        {
                            "id": "llm-security-intel",
                            "workspace": str(tmp_path / "workspace-llm-security-intel"),
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OPENCLAW_GATEWAY_TOKEN", raising=False)
    monkeypatch.setenv("OPENCLAW_HOOKS_TOKEN", "hooks-token")

    settings = sentinel._load_openclaw_settings()

    assert settings.gateway_token is None
    assert settings.gateway_token_source is None


def test_build_connection_snapshot_marks_html_models_response_as_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = _make_runtime_tmp_dir("sentinel-gateway-snapshot")
    config_path = tmp_path / "openclaw.json"
    workspace_root = tmp_path / "workspace-llm-security-intel"
    workspace_root.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "gateway": {"bind": "loopback", "port": 18789, "auth": {"token": "config-token"}},
                "agents": {
                    "list": [
                        {
                            "id": "llm-security-intel",
                            "workspace": str(workspace_root),
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    async def fake_probe(settings: sentinel.OpenClawSettings) -> dict[str, object]:
        return {
            "reachable": True,
            "models_ready": False,
            "content_type": "text/html; charset=utf-8",
            "model_ids": [],
            "server_version": "2026.4.8",
        }

    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(sentinel, "_probe_responses_api", fake_probe)

    snapshot = asyncio.run(sentinel._build_connection_snapshot())

    assert snapshot["status"] == "degraded"
    assert snapshot["preferred_transport"] == "subprocess"
    assert snapshot["gateway"]["responses_url"].endswith("/v1/responses")
    assert snapshot["gateway"]["models_ready"] is False
    assert any("responses.enabled=true" in issue for issue in snapshot["issues"])


def test_flush_and_translate_responses_events_updates_assistant_and_status() -> None:
    run = _make_run()
    ts = sentinel._now_iso()

    delta_event = sentinel._flush_sse_data_lines(
        [
            json.dumps(
                {
                    "type": "response.output_text.delta",
                    "item_id": "item-1",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": "[STATUS] 正在采集 NVD\n第二行回复",
                },
                ensure_ascii=False,
            )
        ]
    )
    assert isinstance(delta_event, dict)
    sentinel._translate_responses_event(run, delta_event, ts)

    completed_event = {
        "type": "response.completed",
        "response": {
            "id": "resp-1",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "[STATUS] 正在采集 NVD\n第二行回复"}],
                }
            ],
        },
    }
    sentinel._translate_responses_event(run, completed_event, ts)

    assert run.gateway_run_id == "resp-1"
    assert run.assistant_text == "[STATUS] 正在采集 NVD\n第二行回复"
    assert any(
        event.payload.get("type") == "node_detail"
        and event.payload.get("message") == "正在采集 NVD"
        for event in run.history
    )
    assert any(
        event.payload.get("type") == "node_verbose"
        and event.payload.get("value") == "第二行回复"
        for event in run.history
    )


def test_flush_sse_data_lines_supports_done_marker() -> None:
    assert sentinel._flush_sse_data_lines(["[DONE]"]) == "[DONE]"


def test_translate_failed_response_emits_error_detail() -> None:
    run = _make_run()
    sentinel._translate_responses_event(
        run,
        {
            "type": "response.failed",
            "response": {
                "id": "resp-err",
                "status": "failed",
                "error": {"message": "gateway failed"},
                "output": [],
            },
        },
        sentinel._now_iso(),
    )

    assert any(
        event.payload.get("type") == "node_error_detail"
        and "gateway failed" in str(event.payload.get("message"))
        for event in run.history
    )


def test_build_openclaw_message_uses_natural_prompt() -> None:
    workspace_root = Path(r"C:\workspace-llm-security-intel")

    message = sentinel._build_openclaw_message("nvd", workspace_root)

    assert "sentinel，为我收集最近7天" in message
    assert "skills" in message
    assert "原生搜索工具" in message
    assert str(workspace_root) in message
    assert sentinel._build_openclaw_command("nvd", workspace_root) not in message
    assert "nvd_collector.py" not in message


def test_run_openclaw_collector_cancel_cancels_pending_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled: dict[str, bool] = {"value": False}

    class _FakeClient:
        def __init__(self, settings: sentinel.OpenClawSettings):
            self.settings = settings

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def complete_response(self, **kwargs: object) -> dict[str, object]:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled["value"] = True
                raise
            return {"status": "completed", "output": []}

    async def fake_connection_snapshot() -> dict[str, object]:
        return {"preferred_transport": "openclaw", "issues": []}

    monkeypatch.setattr(sentinel, "_build_connection_snapshot", fake_connection_snapshot)
    monkeypatch.setattr(sentinel, "_load_openclaw_settings", lambda: _make_settings())
    monkeypatch.setattr(sentinel, "OpenClawResponsesClient", _FakeClient)

    run = _make_run()
    run.cancel_requested = True
    asyncio.run(sentinel._run_openclaw_collector(run))

    assert run.status == "cancelled"


def test_run_openclaw_collector_nonstream_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        def __init__(self, settings: sentinel.OpenClawSettings):
            self.settings = settings

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def complete_response(self, **kwargs: object) -> dict[str, object]:
            return {
                "id": "resp-1",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "[STATUS] 正在采集 NVD\nHEARTBEAT_OK",
                            }
                        ],
                    }
                ],
            }

    async def fake_connection_snapshot() -> dict[str, object]:
        return {"preferred_transport": "openclaw", "issues": []}

    monkeypatch.setattr(sentinel, "_build_connection_snapshot", fake_connection_snapshot)
    monkeypatch.setattr(sentinel, "_load_openclaw_settings", lambda: _make_settings())
    monkeypatch.setattr(sentinel, "OpenClawResponsesClient", _FakeClient)

    run = _make_run()
    asyncio.run(sentinel._run_openclaw_collector(run))

    assert run.status == "succeeded"
    assert run.assistant_text == "[STATUS] 正在采集 NVD\nHEARTBEAT_OK"
    assert any(
        event.payload.get("type") == "run_header"
        for event in run.history
    )
    assert any(
        event.payload.get("type") == "node_detail"
        and event.payload.get("message") == "正在采集 NVD"
        for event in run.history
    )
