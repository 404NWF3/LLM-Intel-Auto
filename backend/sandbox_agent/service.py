"""Durable job adapter; the upstream runtime executes in its own Python environment."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import dotenv_values
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .graph import GraphBuildRequest, export_corpus

ROOT = Path(__file__).resolve().parents[2]
# Retain the installed upstream environment and checkpoint paths during migration.
RUNTIME = ROOT / "backend/red_team/runtime"
TABLES = ("entities", "communities", "community_reports", "text_units", "relationships")


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["audit", "case"] = "audit"
    target_repo: str = Field(default="", max_length=2000)
    authorization_ref: str = Field(default="", max_length=300)
    goal: str = Field(default="审查该 LLM 应用的代码级安全漏洞", max_length=3000)
    request: str = Field(default="", max_length=5000)
    max_rounds: int = Field(default=4, ge=1, le=12)
    max_agent_calls: int = Field(default=30, ge=5, le=200)
    max_cost_usd: float = Field(default=5, gt=0, le=100)
    use_graphrag: bool = True

    @model_validator(mode="after")
    def required_inputs(self):
        if self.kind == "audit" and (
            not self.target_repo or not self.authorization_ref
        ):
            raise ValueError("仓库审计需要本地目录和授权记录")
        if self.kind == "case" and not self.request:
            raise ValueError("请描述离线测试需求")
        return self


class SandboxService:
    def __init__(
        self, data_dir=None, runtime=RUNTIME, popen=subprocess.Popen, intel_store=None
    ):
        self.data_dir = Path(data_dir or ROOT / "data/red_team/runs")
        self.runtime = Path(runtime)
        self.python = (
            self.runtime
            / ".venv"
            / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        self.popen = popen
        self.lock = threading.RLock()
        self.active = None
        self.process = None
        self.intel_store = intel_store
        self.graph_pointer = self.data_dir.parent / "active_graph.json"

    def environment(self):
        # Parent configuration wins. Never read target-repository credentials.
        configured = {
            **dotenv_values(self.runtime / ".env"),
            **dotenv_values(ROOT / ".env"),
        }
        env = {**{k: v for k, v in configured.items() if v is not None}, **os.environ}
        # Reuse the existing intelligence provider without copying or exposing its key.
        if not env.get("DEEPSEEK_CHAT_MODEL") and env.get("DEEPSEEK_API_KEY"):
            env["DEEPSEEK_CHAT_MODEL"] = (
                env.get("DEEPSEEK_MODEL")
                or (
                    env.get("INTEL_SDK_MODEL")
                    if env.get("INTEL_SDK_PROVIDER", "deepseek") == "deepseek"
                    else None
                )
                or "deepseek-flash"
            )
        active_graph = read_json(self.graph_pointer, {})
        if not env.get("RED_TEAM_GRAPH_ROOT") and active_graph.get("root"):
            env["RED_TEAM_GRAPH_ROOT"] = active_graph["root"]
        return env

    def capabilities(self):
        env = self.environment()
        graph_root = (
            Path(env.get("RED_TEAM_GRAPH_ROOT") or self.runtime).expanduser().resolve()
        )
        manifest = read_json(graph_root / "manifest.json", {})
        active_graph = read_json(self.graph_pointer, {})
        if manifest and active_graph.get("root") == str(graph_root):
            manifest.setdefault("run_id", active_graph.get("run_id"))
        native_global = manifest.get("retrieval_mode") == "global"
        index = (
            (graph_root / "settings.yaml").is_file()
            and all(
                (graph_root / "output" / f"{name}.parquet").is_file() for name in TABLES
            )
            and (
                manifest.get("status") == "ready"
                if native_global
                else (graph_root / "output/lancedb").is_dir()
            )
        )
        model = bool(
            env.get("DEEPSEEK_API_KEY", "").strip()
            and env.get("DEEPSEEK_CHAT_MODEL", "").strip()
        )
        endpoint = (
            env.get("DEEPSEEK_ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
            == "https://api.deepseek.com/anthropic"
        )
        graph_keys = all(
            env.get(key, "").strip() for key in ("ZAI_API_KEY", "ZHIPU_API_KEY")
        )
        if native_global:
            graph_keys = model
        ready = self.python.is_file() and model and endpoint
        return {
            "runtime_ready": self.python.is_file(),
            "model_ready": model and endpoint,
            "graph_index_ready": index,
            "graph_credentials_ready": graph_keys,
            "audit_ready": ready,
            "case_ready": ready and index and graph_keys,
            "graph_build_ready": ready and self.intel_store is not None,
            "graph": manifest or None,
            "model": env.get("DEEPSEEK_CHAT_MODEL") or None,
            "graph_root": str(graph_root),
            "families": ["prompt_injection", "long_horizon_dialogue", "tool_hijack"],
        }

    def folder(self, run_id):
        if not re.fullmatch(r"rt_[a-f0-9]{32}", run_id):
            raise HTTPException(404, "任务不存在")
        path = self.data_dir / run_id
        if not (path / "job.json").is_file():
            raise HTTPException(404, "任务不存在")
        return path

    def job(self, run_id):
        job = read_json(self.folder(run_id) / "job.json")
        if job["status"] in {"running", "cancelling"} and run_id != self.active:
            job = {
                **job,
                "status": "interrupted",
                "error": "服务已重启，可恢复已有审计检查点。",
            }
        return job

    def history(self, workspace=None):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for path in self.data_dir.glob("rt_*/job.json"):
            if re.fullmatch(r"rt_[a-f0-9]{32}", path.parent.name):
                job = self.job(path.parent.name)
                if workspace == "graph" and job["kind"] != "graph":
                    continue
                if workspace in {"sandbox", "redteam"} and job["kind"] == "graph":
                    continue
                rows.append(job)
        return sorted(rows, key=lambda row: row["created_at"], reverse=True)[:50]

    def _ready(self, kind):
        cap = self.capabilities()
        if not cap["runtime_ready"]:
            raise HTTPException(
                503,
                "请先运行 uv sync --project backend/red_team/runtime --frozen --group dev",
            )
        if not cap["model_ready"]:
            raise HTTPException(
                503,
                "请在根目录 .env 配置 DEEPSEEK_API_KEY、DEEPSEEK_CHAT_MODEL 和 DeepSeek 官方兼容端点。",
            )
        if kind == "case" and not cap["case_ready"]:
            raise HTTPException(
                503,
                "请先从采集情报构建 GraphRAG，成功后即可生成离线案例。",
            )

    def start(self, config: RunRequest):
        self._ready(config.kind)
        if config.kind == "audit":
            if re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*://|git@)", config.target_repo):
                raise HTTPException(422, "请选择本地仓库目录，不接受远程 URL。")
            target = Path(config.target_repo).expanduser().resolve()
            if not target.is_dir():
                raise HTTPException(422, "本地仓库目录不存在。")
            config.target_repo = str(target)
        with self.lock:
            if self.active:
                raise HTTPException(
                    409, "已有沙盒任务运行中，请等待完成或停止当前任务。"
                )
            rid = f"rt_{uuid4().hex}"
            folder = self.data_dir / rid
            job = {
                "run_id": rid,
                "kind": config.kind,
                "status": "running",
                "created_at": now(),
                "updated_at": now(),
                "title": Path(config.target_repo).name
                if config.kind == "audit"
                else config.request[:80],
                "error": None,
                "config": config.model_dump(),
                "attempts": 1,
                "graph_root": self.capabilities()["graph_root"]
                if config.use_graphrag or config.kind == "case"
                else None,
            }
            write_json(folder / "job.json", job)
            self._launch(job, folder)
            return job

    def start_graph(self, config: GraphBuildRequest):
        self._ready("graph")
        if self.intel_store is None:
            raise HTTPException(503, "情报存储尚未接入")
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有构建或沙盒任务运行中，请等待完成。")
            documents, source = export_corpus(self.intel_store, config)
            rid = f"rt_{uuid4().hex}"
            folder = self.data_dir / rid
            root = folder / "results" / "graph"
            write_json(root / "input/intel_corpus.json", documents)
            write_json(root / "source_manifest.json", source)
            job = {
                "run_id": rid,
                "kind": "graph",
                "status": "running",
                "created_at": now(),
                "updated_at": now(),
                "title": f"情报知识图谱 · {len(documents)} 条",
                "error": None,
                "config": config.model_dump(),
                "attempts": 1,
            }
            write_json(folder / "job.json", job)
            self._launch(job, folder)
            return job

    def checkpoint(self, folder):
        return next(iter(sorted((folder / "results").glob("*/run_state.json"))), None)

    def resume(self, run_id):
        with self.lock:
            job = self.job(run_id)
            self._ready(job["kind"])
            if self.active:
                raise HTTPException(409, "已有沙盒任务运行中。")
            checkpoint = self.checkpoint(self.folder(run_id))
            if (
                job["kind"] != "audit"
                or job["status"] not in {"interrupted", "cancelled", "failed"}
                or not checkpoint
            ):
                raise HTTPException(409, "该任务没有可恢复的审计检查点。")
            state = read_json(checkpoint, {})
            config = job["config"]
            # Resume gets another bounded allowance; retain the original scope and authorization.
            job["resume_caps"] = {
                "max_agent_calls": min(
                    10000, state.get("agent_calls_used", 0) + config["max_agent_calls"]
                ),
                "max_cost_usd": min(
                    500, state.get("cost_usd_used", 0) + config["max_cost_usd"]
                ),
            }
            job.update(
                status="running",
                error=None,
                updated_at=now(),
                attempts=job["attempts"] + 1,
            )
            write_json(self.folder(run_id) / "job.json", job)
            self._launch(job, self.folder(run_id), checkpoint.parent)
            return job

    def _launch(self, job, folder, resume=None):
        command = [
            str(self.python),
            "-u",
            str(Path(__file__).with_name("worker.py")),
            str(folder.resolve()),
        ]
        if resume:
            command += ["--resume", str(resume.resolve())]
        env = self.environment()
        if job.get("graph_root"):
            env["RED_TEAM_GRAPH_ROOT"] = job["graph_root"]
        env["RED_TEAM_PARENT_PID"] = str(os.getpid())
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            with (folder / "runtime.log").open("a", encoding="utf-8") as log:
                process = self.popen(
                    command,
                    cwd=self.runtime,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except (OSError, ValueError):
            job.update(
                status="failed",
                error="无法启动沙盒审计运行环境，请检查依赖安装。",
                updated_at=now(),
            )
            write_json(folder / "job.json", job)
            raise HTTPException(503, job["error"])
        self.active, self.process = job["run_id"], process
        threading.Thread(
            target=self._wait, args=(job, folder, process), daemon=True
        ).start()

    def _wait(self, job, folder, process):
        code = process.wait()
        with self.lock:
            current = read_json(folder / "job.json", job)
            status = (
                "cancelled"
                if current["status"] == "cancelling"
                else {0: "succeeded", 2: "unsupported", 3: "interrupted"}.get(
                    code, "failed"
                )
            )
            error = None
            if status == "failed":
                error = "运行失败，请查看运行记录与后端配置。"
            if status == "unsupported":
                error = "当前意图不受支持，或输入未通过上游校验。"
            if status == "interrupted":
                error = "任务达到预算或中断，已有检查点可恢复。"
            current.update(status=status, error=error, updated_at=now(), exit_code=code)
            if job["kind"] == "graph" and status == "succeeded":
                root = folder / "results" / "graph"
                manifest = read_json(root / "manifest.json", {})
                if manifest.get("status") != "ready" or not manifest.get(
                    "query_verified"
                ):
                    current.update(
                        status="failed", error="图谱未通过检索验证，原索引保持不变。"
                    )
                else:
                    write_json(
                        self.graph_pointer,
                        {
                            "run_id": job["run_id"],
                            "root": str(root.resolve()),
                            "activated_at": now(),
                        },
                    )
            try:
                write_json(folder / "job.json", current)
            finally:
                self.active = self.process = None

    def stop(self, run_id):
        with self.lock:
            job = self.job(run_id)
            if self.active != run_id or not self.process:
                raise HTTPException(409, "该任务当前未运行。")
            job.update(status="cancelling", updated_at=now())
            write_json(self.folder(run_id) / "job.json", job)
            process = self.process
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            threading.Thread(
                target=self._force_stop, args=(process,), daemon=True
            ).start()
            return job

    @staticmethod
    def _force_stop(process):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def shutdown(self):
        if self.active:
            self.stop(self.active)

    def artifacts(self, folder):
        allowed_names = {
            "report.md",
            "findings.json",
            "attack_case.json",
            "attack.py",
            "manifest.json",
            "source_manifest.json",
            "query_check.json",
        }
        result = []
        for path in sorted((folder / "results").rglob("*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.resolve().is_relative_to(folder.resolve())
                and (
                    path.name in allowed_names
                    or (
                        "tests" in path.relative_to(folder / "results").parts
                        and path.suffix in {".py", ".ts", ".js", ".json", ".md"}
                    )
                )
            ):
                result.append(
                    {
                        "path": path.relative_to(folder).as_posix(),
                        "name": path.name,
                        "size": path.stat().st_size,
                    }
                )
        return result

    def artifact_path(self, run_id, name):
        folder = self.folder(run_id)
        if name not in {a["path"] for a in self.artifacts(folder)}:
            raise HTTPException(404, "产物不存在")
        return folder / name

    def detail(self, run_id):
        folder = self.folder(run_id)
        job = self.job(run_id)
        checkpoint = self.checkpoint(folder)
        state = read_json(checkpoint, {}) if checkpoint else {}
        graph_progress = read_json(folder / "graph_progress.json", {})
        case_path = next(iter((folder / "results").glob("*/attack_case.json")), None)
        case = read_json(case_path) if case_path else None
        logs = []
        log_path = folder / "runtime.log"
        if log_path.exists():
            with log_path.open(encoding="utf-8", errors="replace") as stream:
                logs = [line.rstrip()[:2000] for line in deque(stream, maxlen=120)]
        secrets = [
            v
            for k, v in self.environment().items()
            if re.search(r"KEY|TOKEN|SECRET|PASSWORD", k) and len(v) > 6
        ]
        for secret in secrets:
            logs = [line.replace(secret, "[redacted]") for line in logs]
        events = []
        if checkpoint:
            for name in ("events.jsonl", "debate_rounds.jsonl"):
                path = checkpoint.parent / name
                if path.exists():
                    with path.open(encoding="utf-8") as stream:
                        for line in deque(stream, maxlen=80):
                            try:
                                events.append(
                                    {"source": name, "data": json.loads(line)}
                                )
                            except json.JSONDecodeError:
                                continue
        return {
            **job,
            "graph_progress": graph_progress or None,
            "phase": graph_progress.get("phase")
            or state.get("phase")
            or (
                "generating_case"
                if job["kind"] == "case" and job["status"] == "running"
                else job["status"]
            ),
            "state": {
                key: state.get(key)
                for key in (
                    "profile",
                    "threat_surfaces",
                    "hypotheses",
                    "findings",
                    "agent_calls_used",
                    "cost_usd_used",
                    "graph_enabled",
                    "graph_skipped_reason",
                )
            },
            "case": case,
            "logs": logs,
            "events": events,
            "artifacts": self.artifacts(folder),
            "can_resume": bool(
                checkpoint and job["status"] in {"interrupted", "failed", "cancelled"}
            ),
        }
