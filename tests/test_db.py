"""Tests for the SQLite metadata layer: counters and no-reuse of internal_id."""

import aiosqlite
import pytest

from app import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bot.db")
    return tmp_path


async def test_counter_and_distinct_ids(tmp_db):
    await db.init_db()

    # First user: id 1, request 1.
    assert await db.complete_submission(100) == (1, 1)
    # Same user again: id stays, request increments.
    assert await db.complete_submission(100) == (1, 2)
    # Different user: next distinct id, request 1.
    assert await db.complete_submission(200) == (2, 1)


async def test_internal_id_never_reused_after_delete(tmp_db):
    await db.init_db()

    assert await db.complete_submission(100) == (1, 1)
    assert await db.complete_submission(200) == (2, 1)

    # Simulate removing the most-recent user entirely.
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute("DELETE FROM users WHERE telegram_id = 200")
        await conn.commit()

    # A brand-new user must NOT get id 2 again — AUTOINCREMENT moves on.
    internal_id, request_no = await db.complete_submission(300)
    assert internal_id == 3
    assert request_no == 1
