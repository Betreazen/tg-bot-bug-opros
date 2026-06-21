"""Session inactivity timeouts, persisted in Redis so they survive restarts.

Instead of one in-memory asyncio task per user (lost on restart), deadlines are
stored in a Redis hash and a single background sweeper expires stale sessions.
"""

import asyncio
import logging
import time

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from app.config import TIMEOUT_SECONDS
from app.phrases import get_system
from app.keyboards import remove_keyboard

logger = logging.getLogger(__name__)

# Redis hash: field = chat_id (str), value = deadline (epoch seconds, str).
_HASH = "survey:deadlines"
_SWEEP_INTERVAL = 15  # seconds


def _as_str(value) -> str:
    return value.decode() if isinstance(value, (bytes, bytearray)) else value


class TimeoutManager:
    def __init__(self, bot: Bot, storage: BaseStorage, redis) -> None:
        self._bot = bot
        self._storage = storage
        self._redis = redis
        self._task: asyncio.Task | None = None

    async def touch(self, chat_id: int) -> None:
        """Arm/refresh the inactivity deadline for a chat (sliding window)."""
        deadline = time.time() + TIMEOUT_SECONDS
        await self._redis.hset(_HASH, str(chat_id), str(deadline))

    async def cancel(self, chat_id: int) -> None:
        """Drop the deadline (session finished, restarted, or admin)."""
        await self._redis.hdel(_HASH, str(chat_id))

    def start(self) -> None:
        self._task = asyncio.create_task(self._sweep_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _sweep_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_SWEEP_INTERVAL)
                await self._sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Timeout sweep failed")

    async def _sweep_once(self) -> None:
        now = time.time()
        entries = await self._redis.hgetall(_HASH)
        for raw_chat, raw_deadline in entries.items():
            field = _as_str(raw_chat)
            try:
                deadline = float(_as_str(raw_deadline))
            except ValueError:
                await self._redis.hdel(_HASH, field)
                continue
            if deadline <= now:
                await self._expire(int(field))

    async def _expire(self, chat_id: int) -> None:
        # Private chats: chat_id == user_id; matches the dispatcher's StorageKey.
        key = StorageKey(bot_id=self._bot.id, chat_id=chat_id, user_id=chat_id)
        await self._redis.hdel(_HASH, str(chat_id))

        # Free the per-user lock (lazy import avoids a circular dependency).
        try:
            from app.handlers.survey import release_lock
            release_lock(chat_id)
        except Exception:
            pass

        # Only notify if the session is actually still active.
        if await self._storage.get_state(key) is None:
            return
        await self._storage.set_state(key, None)
        await self._storage.set_data(key, {})

        timeout_min = TIMEOUT_SECONDS // 60
        try:
            await self._bot.send_message(
                chat_id,
                get_system("timeout", timeout_min=timeout_min),
                reply_markup=remove_keyboard(),
            )
        except Exception:
            logger.warning("Failed to send timeout notice to %s", chat_id, exc_info=True)


# Module-level singleton wired up in main.py.
manager: TimeoutManager | None = None


async def touch(chat_id: int) -> None:
    if manager is not None:
        await manager.touch(chat_id)


async def cancel(chat_id: int) -> None:
    if manager is not None:
        await manager.cancel(chat_id)
