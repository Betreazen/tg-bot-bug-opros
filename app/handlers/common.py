"""Common handlers: /start command, role routing, out-of-session messages."""

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from app.config import ADMIN_IDS
from app.states import SurveyStates
from app.phrases import get_system, get_question_text
from app.keyboards import admin_menu_keyboard, remove_keyboard
from app.handlers.survey import _cancel_timeout, _reset_timeout

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle /start — route to admin menu or start survey."""
    telegram_id = message.from_user.id

    if telegram_id in ADMIN_IDS:
        # Admin — show admin menu, no survey
        await state.clear()
        await message.answer(
            get_system("admin_menu"),
            reply_markup=admin_menu_keyboard(),
        )
        return

    # Cancel any existing timeout for this user
    _cancel_timeout(telegram_id)

    # User — check if already in survey (restart warning)
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            get_system("restart_warning"),
            reply_markup=remove_keyboard(),
        )

    # Clear state and start fresh
    await state.clear()
    await state.set_state(SurveyStates.q1)
    await state.update_data(
        answers=[],
        q4_texts=[],
        q4_files=[],
        media_group_processed=set(),
    )
    await message.answer(
        get_system("welcome") + "\n\n" + get_question_text(1),
        reply_markup=remove_keyboard(),
    )

    # Start timeout for the new session
    _reset_timeout(telegram_id, state, bot, message.chat.id)
