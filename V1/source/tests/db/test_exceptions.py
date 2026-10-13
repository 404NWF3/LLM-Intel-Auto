from __future__ import annotations

from backend.db.exceptions import (
    ConcurrencyConflictError,
    DuplicateEntityError,
    QueryExecutionError,
    ValidationError,
    map_psycopg_error,
)


class _FakePgError(Exception):
    def __init__(self, message: str, sqlstate: str):
        super().__init__(message)
        self.sqlstate = sqlstate


def test_map_unique_violation_to_duplicate_error() -> None:
    err = _FakePgError("duplicate key", "23505")
    mapped = map_psycopg_error(err)
    assert isinstance(mapped, DuplicateEntityError)


def test_map_check_violation_to_validation_error() -> None:
    err = _FakePgError("check violation", "23514")
    mapped = map_psycopg_error(err)
    assert isinstance(mapped, ValidationError)


def test_map_serialization_to_concurrency_error() -> None:
    err = _FakePgError("serialization failure", "40001")
    mapped = map_psycopg_error(err)
    assert isinstance(mapped, ConcurrencyConflictError)


def test_map_unknown_sqlstate_to_query_error() -> None:
    err = _FakePgError("syntax error", "42601")
    mapped = map_psycopg_error(err, query="SELECT 1")
    assert isinstance(mapped, QueryExecutionError)
    assert "SELECT 1" in str(mapped)

