"""Tests for survey handlers (called directly, bypassing router/filters)."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.handlers import survey
from app.states import SurveyStates
from app.phrases import get_system, get_button
from conftest import make_photo, make_document


# ─── Q1-Q3 text flow ─────────────────────────────────────────────────

async def test_text_answer_advances_state(make_message, fsm, bot):
    msg = make_message(text="my answer")
    await survey.handle_q1(msg, fsm, bot)

    assert await fsm.get_state() == SurveyStates.q2.state
    assert (await fsm.get_data())["answers"] == ["my answer"]
    msg.answer.assert_awaited()


async def test_empty_text_rejected(make_message, fsm, bot):
    msg = make_message(text="   ")
    await survey.handle_q1(msg, fsm, bot)

    msg.answer.assert_awaited_once_with(get_system("empty_answer"))
    assert await fsm.get_state() is None


async def test_non_text_rejected(make_message, fsm, bot):
    msg = make_message(text=None, photo=make_photo())
    await survey.handle_q1(msg, fsm, bot)
    msg.answer.assert_awaited_once_with(get_system("text_expected"))


async def test_forwarded_rejected(make_message, fsm, bot):
    msg = make_message(text="x", forwarded=True)
    await survey.handle_q1(msg, fsm, bot)
    msg.answer.assert_awaited_once_with(get_system("forwarded_rejected"))


async def test_q3_advances_to_q4(make_message, fsm, bot):
    msg = make_message(text="operator")
    await survey.handle_q3(msg, fsm, bot)
    assert await fsm.get_state() == SurveyStates.q4.state


# ─── Q4 media ────────────────────────────────────────────────────────

async def test_q4_photo_stored(make_message, fsm, bot):
    msg = make_message(photo=make_photo("f1"))
    await survey.handle_q4(msg, fsm, bot)
    assert (await fsm.get_data())["q4_files"] == [["f1", ".jpg"]]


async def test_q4_photo_too_big(make_message, fsm, bot):
    msg = make_message(photo=make_photo("f1", file_size=99 * 1024 * 1024))
    await survey.handle_q4(msg, fsm, bot)
    msg.answer.assert_awaited_once_with(get_system("q4_file_too_big"))
    assert (await fsm.get_data()).get("q4_files", []) == []


async def test_q4_image_document_stored(make_message, fsm, bot):
    msg = make_message(document=make_document("d1", "image/png"))
    await survey.handle_q4(msg, fsm, bot)
    assert (await fsm.get_data())["q4_files"] == [["d1", ".png"]]


async def test_q4_non_image_document_rejected(make_message, fsm, bot):
    msg = make_message(document=make_document("d1", "application/pdf"))
    await survey.handle_q4(msg, fsm, bot)
    msg.answer.assert_awaited_once_with(get_system("q4_only_images"))


async def test_q4_plain_text_stored(make_message, fsm, bot):
    msg = make_message(text="some details")
    await survey.handle_q4(msg, fsm, bot)
    assert (await fsm.get_data())["q4_texts"] == ["some details"]


async def test_q4_limit_warns_once(make_message, fsm, bot):
    await fsm.update_data(q4_files=[["a", ".jpg"]] * 5)

    msg1 = make_message(photo=make_photo("f6"))
    await survey.handle_q4(msg1, fsm, bot)
    msg1.answer.assert_awaited_once_with(get_system("q4_max_screenshots"))

    msg2 = make_message(photo=make_photo("f7"))
    await survey.handle_q4(msg2, fsm, bot)
    msg2.answer.assert_not_awaited()  # silent the second time


# ─── Finish ──────────────────────────────────────────────────────────

async def test_finish_empty_asks_confirmation(make_message, fsm, bot):
    msg = make_message(text=get_button("finish"))
    await survey.handle_q4(msg, fsm, bot)
    assert await fsm.get_state() == SurveyStates.q4_confirm_empty.state
    msg.answer.assert_awaited_once()
    assert msg.answer.call_args.args[0] == get_system("q4_confirm_empty")


async def test_finish_with_content_saves(make_message, fsm, bot, monkeypatch):
    monkeypatch.setattr(survey, "build_submission", AsyncMock(return_value="staging"))
    monkeypatch.setattr(survey, "complete_submission", AsyncMock(return_value=(1, 1)))
    monkeypatch.setattr(survey, "finalize_submission", Mock())

    await fsm.update_data(answers=["a", "b", "c"], q4_texts=["note"], q4_files=[])
    msg = make_message(text=get_button("finish"))
    await survey.handle_q4(msg, fsm, bot)

    survey.build_submission.assert_awaited_once()
    survey.complete_submission.assert_awaited_once_with(100)
    survey.finalize_submission.assert_called_once()
    assert await fsm.get_state() is None
    bot.send_message.assert_awaited_once()
    assert "1" in bot.send_message.call_args.args[1]


async def test_finish_save_failure_keeps_session(make_message, fsm, bot, monkeypatch):
    monkeypatch.setattr(
        survey, "build_submission", AsyncMock(side_effect=RuntimeError("disk"))
    )
    await fsm.update_data(answers=["a"], q4_texts=["note"], q4_files=[])
    msg = make_message(text=get_button("finish"))
    await survey.handle_q4(msg, fsm, bot)

    bot.send_message.assert_awaited_once_with(100, get_system("save_failed"))
    # State NOT cleared — user can retry.
    assert (await fsm.get_data())["answers"] == ["a"]


# ─── Empty-confirmation callbacks ────────────────────────────────────

async def test_confirm_empty_yes_saves(make_callback, fsm, bot, monkeypatch):
    monkeypatch.setattr(survey, "build_submission", AsyncMock(return_value="staging"))
    monkeypatch.setattr(survey, "complete_submission", AsyncMock(return_value=(2, 5)))
    monkeypatch.setattr(survey, "finalize_submission", Mock())

    cb = make_callback(data="confirm_empty_yes")
    await survey.confirm_empty_yes(cb, fsm, bot)

    cb.answer.assert_awaited_once()
    cb.message.delete.assert_awaited_once()
    assert await fsm.get_state() is None
    bot.send_message.assert_awaited_once()


async def test_confirm_empty_back_returns_to_q4(make_callback, fsm, bot):
    cb = make_callback(data="confirm_empty_back")
    await survey.confirm_empty_back(cb, fsm, bot)

    assert await fsm.get_state() == SurveyStates.q4.state
    cb.message.answer.assert_awaited_once()
