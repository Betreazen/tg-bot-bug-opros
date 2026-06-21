"""Tests for /start routing in common handlers."""

from app.handlers import common
from app.states import SurveyStates
from app.phrases import get_system


async def test_start_admin_shows_menu(make_message, fsm, bot):
    msg = make_message(text="/start", user_id=1, chat_id=1)  # 1 is in ADMIN_IDS
    await common.cmd_start(msg, fsm, bot)

    assert await fsm.get_state() is None
    assert msg.answer.call_args.args[0] == get_system("admin_menu")


async def test_start_user_begins_survey(make_message, fsm, bot):
    msg = make_message(text="/start", user_id=100, chat_id=100)
    await common.cmd_start(msg, fsm, bot)

    assert await fsm.get_state() == SurveyStates.q1.state
    data = await fsm.get_data()
    assert data["answers"] == [] and data["q4_files"] == []
    assert get_system("welcome") in msg.answer.call_args.args[0]


async def test_start_during_survey_warns(make_message, fsm, bot):
    await fsm.set_state(SurveyStates.q2)
    msg = make_message(text="/start", user_id=100, chat_id=100)
    await common.cmd_start(msg, fsm, bot)

    # First reply is the restart warning, then the fresh survey starts.
    assert msg.answer.await_count == 2
    assert msg.answer.call_args_list[0].args[0] == get_system("restart_warning")
    assert await fsm.get_state() == SurveyStates.q1.state
