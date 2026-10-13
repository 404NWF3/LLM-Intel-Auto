from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_local_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env_file()


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def _default_saads_backend_path() -> str:
    current_repo_backend = Path(__file__).resolve().parents[2]
    legacy_backend = current_repo_backend.parent / "saads-main" / "backend"

    for candidate in (current_repo_backend, legacy_backend):
        if (candidate / "db" / "connection.py").exists():
            return str(candidate)

    return str(current_repo_backend)


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_env: str
    llm_mode: str
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    openai_fast_model: str
    execution_attempts: int
    pass_rate_threshold: float
    feed_source: str
    local_feed_root: str
    saads_main_backend_path: str
    db_feed_min_cvss: float
    db_feed_limit: int
    db_feed_taxonomy_codes: tuple[str, ...]
    db_pool_min_size: int
    db_pool_max_size: int
    db_pool_connect_timeout: int
    db_pool_statement_timeout_ms: int
    db_pool_application_name: str

    @property
    def llm_enabled(self) -> bool:
        return self.llm_mode in {"llm", "auto"}


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    raw_taxonomy_codes = get_env("WP12_DB_FEED_TAXONOMY_CODES", "") or ""
    db_feed_taxonomy_codes = tuple(
        code.strip().upper()
        for code in raw_taxonomy_codes.split(",")
        if code.strip()
    )
    return AppConfig(
        app_env=get_env("APP_ENV", "dev") or "dev",
        llm_mode=(get_env("WP12_LLM_MODE", "rule") or "rule").lower(),
        openai_api_key=get_env("OPENAI_API_KEY"),
        openai_base_url=get_env("OPENAI_BASE_URL"),
        openai_model=get_env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        openai_fast_model=get_env("OPENAI_FAST_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        execution_attempts=int(get_env("WP12_EXECUTION_ATTEMPTS", "5") or "5"),
        pass_rate_threshold=float(get_env("WP12_PASS_RATE_THRESHOLD", "0.8") or "0.8"),
        feed_source=(get_env("WP12_FEED_SOURCE", "mock") or "mock").lower(),
        local_feed_root=(
            get_env("WP12_LOCAL_FEED_ROOT", "saads_wp12/local_feed")
            or "saads_wp12/local_feed"
        ),
        saads_main_backend_path=(
            get_env("SAADS_MAIN_BACKEND_PATH", _default_saads_backend_path())
            or _default_saads_backend_path()
        ),
        db_feed_min_cvss=float(get_env("WP12_DB_FEED_MIN_CVSS", "0") or "0"),
        db_feed_limit=int(get_env("WP12_DB_FEED_LIMIT", "500") or "500"),
        db_feed_taxonomy_codes=db_feed_taxonomy_codes,
        db_pool_min_size=int(get_env("WP12_DB_POOL_MIN_SIZE", "1") or "1"),
        db_pool_max_size=int(get_env("WP12_DB_POOL_MAX_SIZE", "2") or "2"),
        db_pool_connect_timeout=int(get_env("WP12_DB_POOL_CONNECT_TIMEOUT", "10") or "10"),
        db_pool_statement_timeout_ms=int(
            get_env("WP12_DB_POOL_STATEMENT_TIMEOUT_MS", "60000") or "60000"
        ),
        db_pool_application_name=(
            get_env("WP12_DB_POOL_APPLICATION_NAME", "saads-wp12-batch")
            or "saads-wp12-batch"
        ),
    )
