"""WP1-3 routes, with a shared-service alias for existing red-team clients."""

from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from .graph import GraphBuildRequest
from .service import SandboxService, RunRequest


def create_router(service: SandboxService, *, legacy: bool = False):
    router = APIRouter(
        prefix="/api/redteam" if legacy else "/api/sandbox",
        tags=["Sandbox"],
        deprecated=legacy,
    )

    @router.get("/overview")
    def overview():
        history = service.history()
        active = service.active
        return {
            "capabilities": service.capabilities(),
            "active_run_id": active,
            "active_run_kind": service.job(active)["kind"] if active else None,
            "recent_run_count": len(history),
            "recent_completed_count": sum(
                row["status"] == "succeeded" for row in history
            ),
        }

    @router.get("/runs")
    def runs(workspace: Literal["sandbox", "redteam", "graph"] | None = None):
        return service.history(workspace=workspace)

    @router.post("/runs", status_code=202)
    def start(config: RunRequest):
        return service.start(config)

    @router.post("/graph/build", status_code=202)
    def build_graph(config: GraphBuildRequest):
        return service.start_graph(config)

    @router.get("/runs/{run_id}")
    def detail(run_id: str):
        return service.detail(run_id)

    @router.post("/runs/{run_id}/stop")
    def stop(run_id: str):
        return service.stop(run_id)

    @router.post("/runs/{run_id}/resume", status_code=202)
    def resume(run_id: str):
        return service.resume(run_id)

    @router.get("/runs/{run_id}/artifact")
    def artifact(run_id: str, path: str = Query(min_length=1, max_length=500)):
        file = service.artifact_path(run_id, path)
        return FileResponse(
            file,
            media_type="text/plain; charset=utf-8",
            filename=file.name,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return router
