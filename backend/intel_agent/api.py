"""Local HTTP adapter for the existing collection engine (one worker).

Run from the repository root with ``uv run intel-api``.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from common.topics import ALL_SECURITY_TOPICS, CORE_SECURITY_TOPICS
from .engine.controller import IntelAgentController
from .engine.modes import FullCollectionMode, IncrementalCollectionMode
from .observability import TraceSink, format_event_line
from .schemas import RunBudget
from .store import default_store


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CollectionRequest(BaseModel):
    mode: Literal["full", "incremental"] = "incremental"
    focus: str = Field(default="", max_length=300)
    window_days: int = Field(default=1, ge=1, le=365)
    max_rounds: int = Field(default=6, ge=1)
    max_api_calls: int = Field(default=40, ge=1)


class CollectionService:
    def __init__(self, store=None, controller_factory=IntelAgentController,
                 data_dir: Path = Path("data/intel_agent")):
        self.store = store if store is not None else default_store()
        self.controller_factory = controller_factory
        self.data_dir = data_dir
        self.lock = threading.RLock()
        self.active: dict[str, Any] | None = None

    def _save(self, job):
        folder = self.data_dir / "web_jobs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{job['run_id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def jobs(self):
        result = []
        for path in (self.data_dir / "web_jobs").glob("*.json"):
            job = json.loads(path.read_text(encoding="utf-8"))
            if job["status"] == "running":
                with self.lock:
                    if self.active and self.active["run_id"] == job["run_id"]:
                        job = dict(self.active)
                    else:
                        job = {**job, "status": "interrupted", "error": "API 服务已重启，任务中断；可重新发起采集。"}
            result.append(job)
        return result

    def history(self):
        rows = {row["run_id"]: row for row in self.store.list_run_summaries(limit=50)}
        for job in self.jobs():
            rid = job["run_id"]
            # Persisted engine status is authoritative; journal adds failures/interruption.
            rows[rid] = {**job, **rows.get(rid, {})}
        return sorted(rows.values(), key=lambda row: row.get("saved_at") or "", reverse=True)[:50]

    def start(self, config: CollectionRequest):
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有采集任务运行中，请等待完成。")
            job = {"run_id": f"web_{uuid4().hex}", "status": "running", "saved_at": now(),
                   "run_mode": config.mode, "config": config.model_dump(), "item_count": 0,
                   "rounds": 0, "api_calls_used": 0, "error": None}
            self._save(job)
            self.active = job
            try:
                threading.Thread(target=self._run, args=(job, config), daemon=True).start()
            except Exception:
                self.active = None
                job.update(status="failed", error="无法启动采集线程")
                self._save(job)
                raise
            return dict(job)

    def _run(self, job, config):
        def on_event(event):
            with self.lock:
                if event.get("event") in {"round_start", "round_summary"}:
                    job["rounds"] = event.get("round", job["rounds"])
                if "api_calls_used" in event:
                    job["api_calls_used"] = event["api_calls_used"]

        trace = TraceSink(console=False, trace_dir=self.data_dir / "traces", on_event=on_event)
        try:
            mode = (FullCollectionMode() if config.mode == "full" else
                    IncrementalCollectionMode(focus=config.focus.strip() or None,
                                              window_days=config.window_days))
            bb = self.controller_factory(store=self.store).run(
                mode=mode, budget=RunBudget(max_rounds=config.max_rounds,
                                           max_api_calls=config.max_api_calls),
                run_id=job["run_id"], trace=trace)
            degraded = any(error.error_type == "persistence_fallback" for error in bb.errors)
            job.update(status="partial_success" if degraded or not bb.raw_items else "succeeded",
                       item_count=len(bb.raw_items), rounds=len(bb.query_history),
                       api_calls_used=bb.metrics.api_calls_used, stop_reason=bb.stop_reason,
                       error="主存储写入失败，结果已回退到 data/intel_runs。" if degraded else None)
        except Exception:
            logging.exception("Collection %s failed", job["run_id"])
            job.update(status="failed", error="采集失败，请检查后端终端日志与来源／模型配置。")
        finally:
            trace.close()
            with self.lock:
                job["saved_at"] = now()
                try:
                    self._save(job)
                finally:
                    self.active = None


def create_app(service: CollectionService | None = None, researcher_service=None, pentest_service=None):
    service = service or CollectionService()
    app = FastAPI(title="LLM 安全情报采集 API")
    app.state.collection = service
    from sandbox_agent.api import create_router
    from sandbox_agent.service import SandboxService
    sandbox = SandboxService(intel_store=service.store)
    app.state.sandbox = sandbox
    app.state.red_team = sandbox  # Compatibility: one service, lock and history.
    app.include_router(create_router(sandbox))
    app.include_router(create_router(sandbox, legacy=True))
    app.add_event_handler("shutdown", sandbox.shutdown)
    from .researcher.api import create_router as researcher_router
    from .researcher.service import ResearcherService
    researcher = researcher_service or ResearcherService()
    app.state.researcher = researcher
    app.include_router(researcher_router(researcher))
    app.add_event_handler("shutdown", researcher.shutdown)
    from pentest_agent.api import create_router as pentest_router
    from pentest_agent.service import PentestService
    pentest = pentest_service or PentestService(intel_store=service.store)
    app.state.pentest = pentest
    app.include_router(pentest_router(pentest))
    app.add_event_handler("shutdown", pentest.shutdown)

    @app.exception_handler(Exception)
    async def unavailable(request: Request, exc: Exception):
        logging.error("Intel API failure", exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "情报存储暂不可用，请检查后端服务日志。"})

    @app.get("/api/intel/overview")
    def overview():
        latest = service.store.load_latest_payload()
        bb = (latest or {}).get("blackboard") or {}
        counts = {topic: 0 for topic in CORE_SECURITY_TOPICS}
        for item in bb.get("raw_items", []):
            for topic in set((item.get("metadata") or {}).get("topics") or []):
                if topic in counts:
                    counts[topic] += 1
        with service.lock:
            active = dict(service.active) if service.active else None
        return {"active": active, "item_count": service.store.distinct_item_count(),
                "run_count": service.store.run_count(),
                "sources": service.store.distinct_sources(), "topics": ALL_SECURITY_TOPICS,
                "coverage": counts, "latest": None if not latest else {
                    "run_id": latest["run_id"], "status": latest.get("status"),
                    "saved_at": latest.get("saved_at"), "summary": latest.get("summary", {}),
                }}

    @app.get("/api/intel/runs")
    def runs():
        return service.history()

    @app.post("/api/intel/runs", status_code=202)
    def start(config: CollectionRequest):
        return service.start(config)

    @app.get("/api/intel/runs/{run_id}")
    def detail(run_id: str):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,149}", run_id):
            raise HTTPException(400, "无效的任务 ID")
        try:
            payload = service.store.load_run_payload(run_id)
        except FileNotFoundError:
            payload = None
        job = next((job for job in service.jobs() if job["run_id"] == run_id), None)
        if not payload and not job:
            raise HTTPException(404, "任务不存在")
        path = service.data_dir / "traces" / f"{run_id}.jsonl"
        events = []
        if path.exists():
            with path.open(encoding="utf-8") as stream:
                for line in deque(stream, maxlen=300):
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # A concurrent trace append may be incomplete.
                    events.append({"ts": record.get("ts"), "event": record.get("event"),
                                   "message": format_event_line(record) or json.dumps(record, ensure_ascii=False)[:1200]})
        bb = (payload or {}).get("blackboard") or {}
        return {"run_id": run_id, "status": (payload or job)["status"],
                "error": (job or {}).get("error"), "summary": (payload or {}).get("summary", {"rounds": (job or {}).get("rounds", 0)}),
                "metrics": bb.get("metrics", {"api_calls_used": (job or {}).get("api_calls_used", 0)}), "events": events,
                "errors": bb.get("errors", [])}

    @app.get("/api/intel/items")
    def items(text: str = Query("", max_length=200), source: str = "", topic: str = "",
              run_id: str = "", limit: int = Query(100, ge=1, le=200)):
        import re
        # Mongo's store treats text as regex; HTTP searches use literal text.
        needle = re.escape(text) if service.store.store_backend().startswith("mongodb:") else text
        rows = service.store.query_items(text=needle, source_name=source, topic=topic,
                                         run_id=run_id, limit=limit)
        fields = ("item_id", "title", "summary", "source_name", "source_uri", "published_at", "relevance_score", "topics")
        return [{key: row.get(key) for key in fields} for row in rows]

    @app.get("/api/intel/export")
    def export_items():
        exported_at = datetime.now(timezone.utc)
        rows = service.store.query_items(limit=None)
        # Match the full detail response, omitting only Mongo's internal key.
        items = [{key: value for key, value in row.items() if key != "_id"} for row in rows]
        return JSONResponse(
            content=jsonable_encoder({
                "format": "intel-agent.items.v1",
                "exported_at": exported_at.isoformat(),
                "item_count": len(items),
                "items": items,
            }),
            headers={
                "Content-Disposition": f'attachment; filename="intel-agent-items-{exported_at:%Y%m%dT%H%M%SZ}.json"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/intel/items/{item_id:path}")
    def item_detail(item_id: str):
        row = service.store.get_item(item_id)
        if row is None:
            raise HTTPException(404, "情报不存在")
        return {key: value for key, value in row.items() if key != "_id"}

    return app


def main():
    import uvicorn
    uvicorn.run("intel_agent.api:create_app", factory=True, host="127.0.0.1", port=8001, workers=1)
