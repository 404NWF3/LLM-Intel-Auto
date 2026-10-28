"""Separate process so Stop terminates training and model-planning children."""
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from .loop import run_research
from .schemas import ResearchRequest
from .service import now, read_json, write_json


def main():
    def watch_parent():
        parent = int(os.environ.get("RESEARCHER_PARENT_PID", "0"))
        while parent and os.name != "nt":
            if os.getppid() != parent:
                os.killpg(os.getpgrp(), signal.SIGTERM)
                return
            time.sleep(1)

    threading.Thread(target=watch_parent, daemon=True).start()
    folder, dataset_path = map(Path, sys.argv[1:3])
    path = folder / "job.json"
    job = read_json(path)

    def progress(patch):
        job.update(patch)
        job["updated_at"] = now()
        if patch.get("message"):
            job["events"].append({"ts": now(), "message": patch["message"]})
            job["events"] = job["events"][-100:]
        write_json(path, job)

    try:
        result = run_research(ResearchRequest.model_validate(job["config"]), dataset_path, folder, progress)
        progress({**result, "status": "succeeded", "message": "循环完成，最佳模型和异常分数已保存"})
    except Exception:
        logging.exception("Researcher worker failed")
        progress({"status": "failed", "error": "研究运行失败，请检查后端日志", "message": "任务失败"})
        raise SystemExit(1)


if __name__ == "__main__":
    main()
