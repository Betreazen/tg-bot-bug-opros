"""Shared test setup: env vars, phrase loading, and mock factories.

aiogram has no wheels for very new Python versions, so when it can't be
imported we skip the handler/storage/timeout tests (they run in Docker/CI on
Python 3.12). The pure-logic tests still run everywhere.
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# app.config reads these at import time — set them before any test imports it.
os.environ.setdefault("BOT_TOKEN", "12345:test-token")
os.environ.setdefault("ADMIN_IDS", "1,2")
os.environ.setdefault("DATA_DIR", "./_test_data")

from app import phrases as _phrases  # noqa: E402  (after env setup)

# Skip aiogram-dependent suites when aiogram isn't installed.
collect_ignore: list[str] = []
try:
    import aiogram  # noqa: F401
except ImportError:
    collect_ignore += [
        "test_storage.py",
        "test_survey.py",
        "test_timeouts.py",
        "test_common.py",
        "test_admin.py",
    ]


@pytest.fixture(autouse=True, scope="session")
def _load_phrases():
    _phrases.load_phrases()


@pytest.fixture
def make_message():
    """Factory for a Message-like object handlers can be called with directly."""
    def _make(
        text=None,
        photo=None,
        document=None,
        caption=None,
        chat_id=100,
        user_id=100,
        forwarded=False,
        media_group_id=None,
    ):
        msg = SimpleNamespace()
        msg.text = text
        msg.photo = photo
        msg.document = document
        msg.caption = caption
        msg.media_group_id = media_group_id
        msg.forward_origin = "fwd" if forwarded else None
        msg.forward_date = None
        msg.chat = SimpleNamespace(id=chat_id)
        msg.from_user = SimpleNamespace(id=user_id)
        msg.answer = AsyncMock()
        msg.answer_document = AsyncMock()
        msg.delete = AsyncMock()
        return msg

    return _make


@pytest.fixture
def make_callback(make_message):
    """Factory for a CallbackQuery-like object."""
    def _make(data="confirm_empty_yes", chat_id=100, user_id=100):
        cb = SimpleNamespace()
        cb.data = data
        cb.from_user = SimpleNamespace(id=user_id)
        cb.message = make_message(chat_id=chat_id, user_id=user_id)
        cb.answer = AsyncMock()
        return cb

    return _make


@pytest.fixture
def fsm():
    """A real FSMContext backed by in-memory storage."""
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=100, user_id=100)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
def bot():
    """A Bot-like stub with the methods handlers/timeouts use."""
    return SimpleNamespace(id=42, send_message=AsyncMock())


def make_photo(file_id="ph1", file_size=1000):
    return [SimpleNamespace(file_id=file_id, file_size=file_size)]


def make_document(file_id="doc1", mime_type="image/png", file_size=1000):
    return SimpleNamespace(file_id=file_id, mime_type=mime_type, file_size=file_size)
