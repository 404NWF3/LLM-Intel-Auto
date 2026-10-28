"""Compatibility route factory. New callers should use sandbox_agent.api."""

from sandbox_agent.api import create_router as sandbox_router


def create_router(service):
    return sandbox_router(service, legacy=True)
