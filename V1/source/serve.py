"""serve.py — SUFE-SAADS 后端 API 服务器启动入口

用法：
  python serve.py               # 默认 0.0.0.0:8000，热重载
  python serve.py --port 9000   # 自定义端口
  python serve.py --no-reload   # 生产模式（关闭热重载）
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


_BACKEND_DIR = str(Path(__file__).resolve().parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
_existing_pythonpath = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    _BACKEND_DIR + os.pathsep + _existing_pythonpath
    if _existing_pythonpath
    else _BACKEND_DIR
)

from dotenv import load_dotenv

# 加载项目根目录的 .env（必须在任何 backend 模块导入之前）
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="SUFE-SAADS API Server")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址 (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="端口 (default: 8000)")
    parser.add_argument("--no-reload", action="store_true", help="关闭热重载（生产模式）")
    args = parser.parse_args()

    uvicorn.run(
        "backend.api.server:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=["backend"],
    )


if __name__ == "__main__":
    main()
