from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .data import MAX_BYTES, demo_csv
from .schemas import ResearchRequest
from .service import ResearcherService


def create_router(service: ResearcherService):
    router = APIRouter(prefix="/api/researcher", tags=["Researcher"])

    @router.get("/overview")
    def overview():
        return service.overview()

    @router.get("/datasets")
    def datasets():
        return service.datasets()

    @router.post("/datasets", status_code=201)
    async def upload(request: Request, filename: str = Query("dataset.csv", max_length=300)):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise HTTPException(413, "CSV 文件不能超过 8 MiB")
        return service.upload(bytes(body), filename)

    @router.post("/datasets/demo", status_code=201)
    def demo():
        return service.upload(demo_csv(), "demo-synthetic.csv")

    @router.get("/runs")
    def history():
        return service.history()

    @router.post("/runs", status_code=202)
    def start(config: ResearchRequest):
        return service.start(config)

    @router.get("/runs/{run_id}")
    def detail(run_id: str):
        return service.job(run_id)

    @router.post("/runs/{run_id}/stop")
    def stop(run_id: str):
        return service.stop(run_id)

    @router.get("/runs/{run_id}/model")
    def model(run_id: str):
        return FileResponse(service.artifact(run_id, "model.joblib"),
                            filename=f"{run_id}.joblib", media_type="application/octet-stream")

    @router.get("/runs/{run_id}/scores")
    def scores(run_id: str):
        return FileResponse(service.artifact(run_id, "scores.csv"),
                            filename=f"{run_id}-scores.csv", media_type="text/csv")

    return router
