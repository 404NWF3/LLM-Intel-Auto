"""One local Researcher worker, with durable progress and cancellation."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from ..runtime.client import main_model, sdk_runtime_available
from .data import describe, load_dataset
from .schemas import ResearchRequest

ROOT = Path(__file__).resolve().parents[3]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


class ResearcherService:
    def __init__(self, data_dir: Path | None = None, max_run_seconds: int = 900):
        self.data_dir = Path(data_dir or ROOT / "data/researcher").resolve()
        self.max_run_seconds = max_run_seconds
        self.lock = threading.RLock()
        self.active: str | None = None
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.cancel_requested = False

    def datasets(self):
        rows = [read_json(path) for path in (self.data_dir / "datasets").glob("ds_*.json")]
        return sorted((row for row in rows if row), key=lambda row: row.get("created_at", ""),
                      reverse=True)[:50]

    def upload(self, content: bytes, filename: str):
        dataset_id = f"ds_{uuid4().hex}"
        name = filename.replace("\\", "/").rsplit("/", 1)[-1][:128] or "dataset.csv"
        try:
            metadata = describe(content, dataset_id, name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        folder = self.data_dir / "datasets"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{dataset_id}.csv").write_bytes(content)
        metadata["created_at"] = now()
        write_json(folder / f"{dataset_id}.json", metadata)
        return metadata

    def dataset(self, dataset_id: str):
        if not re.fullmatch(r"ds_[a-f0-9]{32}", dataset_id):
            raise HTTPException(404, "数据集不存在")
        path = self.data_dir / "datasets" / f"{dataset_id}.csv"
        metadata = read_json(path.with_suffix(".json"))
        if not metadata or not path.is_file():
            raise HTTPException(404, "数据集不存在，请重新上传 CSV")
        return path, metadata

    def folder(self, run_id: str):
        if not re.fullmatch(r"research_[a-f0-9]{32}", run_id):
            raise HTTPException(404, "研究任务不存在")
        folder = self.data_dir / "runs" / run_id
        if not (folder / "job.json").is_file():
            raise HTTPException(404, "研究任务不存在")
        return folder

    def job(self, run_id: str):
        with self.lock:
            folder = self.folder(run_id)
            job = read_json(folder / "job.json")
            if not job:
                raise HTTPException(503, "任务记录暂不可读")
            if job["status"] == "running":
                if run_id != self.active:
                    job.update(status="interrupted", error="服务已重启，任务中断；可重新开始。")
                elif self.cancel_requested:
                    job["status"] = "cancelling"
            job["artifacts_ready"] = (job["status"] == "succeeded"
                                      and (folder / "model.joblib").is_file()
                                      and (folder / "scores.csv").is_file())
            return job

    def history(self):
        folders = sorted((self.data_dir / "runs").glob("research_*/job.json"),
                         key=lambda path: path.stat().st_mtime, reverse=True)[:50]
        return [self.job(path.parent.name) for path in folders]

    def overview(self):
        available, _ = sdk_runtime_available()
        with self.lock:
            return {"active": self.job(self.active) if self.active else None,
                    "run_count": sum(1 for _ in (self.data_dir / "runs").glob("research_*/job.json")),
                    "llm_available": available, "model": main_model()}

    def start(self, config: ResearchRequest):
        with self.lock:
            if self.active:
                raise HTTPException(409, "已有 Researcher 任务运行中，请完成或停止后再开始。")
            dataset_path, metadata = self.dataset(config.dataset_id)
            try:
                load_dataset(dataset_path, config.label_column)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            run_id = f"research_{uuid4().hex}"
            folder = self.data_dir / "runs" / run_id
            job = {"run_id": run_id, "status": "running", "created_at": now(), "updated_at": now(),
                   "config": config.model_dump(), "dataset": metadata, "current_round": 0,
                   "rounds": [], "best_round": None, "metric": None, "evaluation_note": "",
                   "message": "准备数据与固定评估划分", "events": [], "final_metrics": None,
                   "error": None, "artifacts_ready": False}
            write_json(folder / "job.json", job)
            env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                   "MKL_NUM_THREADS": "1", "PYTHONUNBUFFERED": "1",
                   "RESEARCHER_PARENT_PID": str(os.getpid())}
            # Also works from a source checkout without relying on a globally installed package.
            env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")
            self.active, self.cancel_requested = run_id, False
            try:
                with (folder / "worker.log").open("w", encoding="utf-8") as output:
                    self.process = subprocess.Popen(
                        [sys.executable, "-m", "intel_agent.researcher.worker", str(folder), str(dataset_path)],
                        cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                        start_new_session=os.name != "nt",
                    )
                self.thread = threading.Thread(target=self._watch, args=(run_id, self.process), daemon=True)
                self.thread.start()
            except Exception:
                if self.process:
                    self._terminate(self.process, force=True)
                self.active, self.process = None, None
                job.update(status="failed", error="无法启动 Researcher 工作进程")
                write_json(folder / "job.json", job)
                raise HTTPException(503, job["error"])
            return job

    @staticmethod
    def _terminate(process, force=False):
        try:
            if os.name == "nt":
                process.kill() if force else process.terminate()
            else:
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass

    def _watch(self, run_id, process):
        timed_out = False
        try:
            process.wait(timeout=self.max_run_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate(process, force=True)
            process.wait()
        with self.lock:
            path = self.folder(run_id) / "job.json"
            job = read_json(path)
            if self.cancel_requested:
                job.update(status="cancelled", message="任务已停止，已完成轮次已保留", error=None)
            elif timed_out:
                job.update(status="failed", error="任务超过 15 分钟运行上限，已停止")
            elif process.returncode != 0 or job["status"] == "running":
                job.update(status="failed", error=job.get("error") or "工作进程异常退出，请检查后端日志")
            job["updated_at"] = now()
            write_json(path, job)
            self.active, self.process = None, None

    def stop(self, run_id: str):
        with self.lock:
            self.folder(run_id)
            if self.active == run_id and self.process:
                self.cancel_requested = True
                self._terminate(self.process)
                # Enforce cancellation even if a native operation ignores SIGTERM.
                threading.Thread(target=self._ensure_stopped, args=(self.process,), daemon=True).start()
            return self.job(run_id)

    def _ensure_stopped(self, process):
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._terminate(process, force=True)

    def shutdown(self):
        with self.lock:
            if self.active:
                self.stop(self.active)
            thread = self.thread
        if thread:
            thread.join(timeout=5)

    def artifact(self, run_id: str, filename: str):
        folder = self.folder(run_id)
        if filename not in {"model.joblib", "scores.csv"} or not self.job(run_id)["artifacts_ready"]:
            raise HTTPException(404, "任务成功完成后可下载结果")
        return folder / filename
