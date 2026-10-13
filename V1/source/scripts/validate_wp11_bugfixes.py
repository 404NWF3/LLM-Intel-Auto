from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(dotenv_path=ROOT / ".env", override=False)

from backend.wp11_bugfix_validator import run_wp11_bugfix_suite


def main() -> None:
    raise SystemExit(run_wp11_bugfix_suite())


if __name__ == "__main__":
    main()
