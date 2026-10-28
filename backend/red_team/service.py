"""Compatibility imports; WP1-3 owns the service and its existing storage."""

from sandbox_agent.service import (
    ROOT,
    RUNTIME,
    TABLES,
    RunRequest,
    SandboxService,
    now,
    read_json,
    write_json,
)

RedTeamService = SandboxService

__all__ = [
    "ROOT", "RUNTIME", "TABLES", "RunRequest", "RedTeamService",
    "now", "read_json", "write_json",
]
