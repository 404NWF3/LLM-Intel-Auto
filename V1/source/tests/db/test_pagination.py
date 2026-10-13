from __future__ import annotations

import pytest

from backend.db.exceptions import ValidationError
from backend.db.pagination import Pagination


def test_pagination_to_sql() -> None:
    p = Pagination(limit=25, offset=50)
    sql, params = p.to_sql()
    assert sql.strip().upper() == "LIMIT %S OFFSET %S"
    assert params == (25, 50)


def test_pagination_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Pagination(limit=0, offset=0)


def test_pagination_offset_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        Pagination(limit=10, offset=-1)

