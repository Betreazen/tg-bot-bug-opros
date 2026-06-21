"""Tests for admin export handler."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from app.handlers import admin
from app.phrases import get_system, get_button


@pytest.fixture
def fsm_stub():
    # admin_handler doesn't touch FSM, but its signature requires it.
    return None


async def test_export_sends_zip(make_message, fsm_stub, bot, tmp_path, monkeypatch):
    zip_path = tmp_path / "export.zip"
    zip_path.write_bytes(b"PK\x03\x04zip")
    monkeypatch.setattr(admin, "build_export_zip", Mock(return_value=(zip_path, True)))

    msg = make_message(text=get_button("export_db"), user_id=1)
    await admin.admin_handler(msg, fsm_stub, bot)

    msg.answer_document.assert_awaited_once()
    # Temp archive is cleaned up after sending.
    assert not zip_path.exists()


async def test_export_empty(make_message, fsm_stub, bot, monkeypatch):
    monkeypatch.setattr(admin, "build_export_zip", Mock(return_value=(None, False)))
    msg = make_message(text=get_button("export_db"), user_id=1)
    await admin.admin_handler(msg, fsm_stub, bot)
    msg.answer.assert_awaited_once_with(get_system("export_empty"))


async def test_export_too_big(make_message, fsm_stub, bot, tmp_path, monkeypatch):
    zip_path = tmp_path / "export.zip"
    zip_path.write_bytes(b"huge")
    monkeypatch.setattr(admin, "build_export_zip", Mock(return_value=(zip_path, False)))

    msg = make_message(text=get_button("export_db"), user_id=1)
    await admin.admin_handler(msg, fsm_stub, bot)

    msg.answer.assert_awaited_once_with(get_system("export_too_big"))
    assert not zip_path.exists()  # cleaned up even when not sent


async def test_non_export_shows_menu(make_message, fsm_stub, bot):
    msg = make_message(text="random", user_id=1)
    await admin.admin_handler(msg, fsm_stub, bot)
    assert msg.answer.call_args.args[0] == get_system("admin_menu")
