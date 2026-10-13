from __future__ import annotations

from backend.db.unit_of_work import UnitOfWork


class _FakeConn:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_uow_commits_on_success() -> None:
    conn = _FakeConn()
    with UnitOfWork(conn=conn):
        pass
    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_uow_rolls_back_on_failure() -> None:
    conn = _FakeConn()
    try:
        with UnitOfWork(conn=conn):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert conn.commits == 0
    assert conn.rollbacks == 1

