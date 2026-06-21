"""Tests for the Redis-backed inactivity timeout manager (fake redis)."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import timeouts
from app.timeouts import TimeoutManager, _HASH


class FakeRedis:
    """Minimal async stand-in supporting the hash ops the manager uses."""

    def __init__(self):
        self.store: dict[str, dict[str, str]] = {}

    async def hset(self, name, key, value):
        self.store.setdefault(name, {})[str(key)] = str(value)

    async def hdel(self, name, *keys):
        bucket = self.store.get(name, {})
        for k in keys:
            bucket.pop(str(k), None)

    async def hgetall(self, name):
        return dict(self.store.get(name, {}))


@pytest.fixture
def storage():
    from aiogram.fsm.storage.memory import MemoryStorage
    return MemoryStorage()


@pytest.fixture
def key():
    from aiogram.fsm.storage.base import StorageKey
    return StorageKey(bot_id=42, chat_id=100, user_id=100)


@pytest.fixture
def manager(storage):
    bot = SimpleNamespace(id=42, send_message=AsyncMock())
    return TimeoutManager(bot, storage, FakeRedis())


async def test_touch_then_cancel(manager):
    await manager.touch(100)
    assert "100" in manager._redis.store[_HASH]
    await manager.cancel(100)
    assert "100" not in manager._redis.store.get(_HASH, {})


async def test_sweep_expires_active_session(manager, storage, key):
    await storage.set_state(key, "SurveyStates:q1")
    await manager._redis.hset(_HASH, "100", str(time.time() - 1))  # already past

    await manager._sweep_once()

    manager._bot.send_message.assert_awaited_once()
    assert await storage.get_state(key) is None
    assert "100" not in manager._redis.store.get(_HASH, {})


async def test_sweep_keeps_future_session(manager, storage, key):
    await storage.set_state(key, "SurveyStates:q1")
    await manager._redis.hset(_HASH, "100", str(time.time() + 999))

    await manager._sweep_once()

    manager._bot.send_message.assert_not_awaited()
    assert await storage.get_state(key) == "SurveyStates:q1"


async def test_expire_without_state_does_not_notify(manager):
    await manager._redis.hset(_HASH, "100", str(time.time() - 1))

    await manager._sweep_once()

    manager._bot.send_message.assert_not_awaited()
    assert "100" not in manager._redis.store.get(_HASH, {})


async def test_module_helpers_noop_without_manager(monkeypatch):
    monkeypatch.setattr(timeouts, "manager", None)
    # Should not raise.
    await timeouts.touch(1)
    await timeouts.cancel(1)
