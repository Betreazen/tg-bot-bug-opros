"""SQLite database layer for user/submission metadata."""

import aiosqlite
from pathlib import Path
from datetime import datetime, timezone

from app.config import DATA_DIR


DB_PATH: Path = DATA_DIR / "bot.db"


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id     INTEGER PRIMARY KEY,
                internal_id     INTEGER UNIQUE NOT NULL,
                last_request_no INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT    NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                internal_id INTEGER NOT NULL,
                request_no  INTEGER NOT NULL,
                created_at  TEXT    NOT NULL
            )
        """)
        await db.commit()


async def complete_submission(telegram_id: int) -> tuple[int, int]:
    """
    Atomically assign/reuse internal_id and increment request counter.

    Returns (internal_id, request_no) for the new submission.
    """
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                "SELECT internal_id, last_request_no FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cursor.fetchone()

            if row is None:
                # New user — assign next internal_id
                cursor = await db.execute(
                    "SELECT COALESCE(MAX(internal_id), 0) + 1 FROM users"
                )
                next_id_row = await cursor.fetchone()
                internal_id = next_id_row[0]
                request_no = 1

                await db.execute(
                    "INSERT INTO users (telegram_id, internal_id, last_request_no, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (telegram_id, internal_id, request_no, now),
                )
            else:
                internal_id = row[0]
                request_no = row[1] + 1

                await db.execute(
                    "UPDATE users SET last_request_no = ? WHERE telegram_id = ?",
                    (request_no, telegram_id),
                )

            # Record in submissions journal
            await db.execute(
                "INSERT INTO submissions (internal_id, request_no, created_at) "
                "VALUES (?, ?, ?)",
                (internal_id, request_no, now),
            )

            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return internal_id, request_no
