"""Admin handlers: admin menu and database export."""

from aiogram import Router, F, Bot
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext

from app.config import ADMIN_IDS
from app.phrases import get_system, get_button
from app.keyboards import admin_menu_keyboard
from app.export import build_export_zip

router = Router()


@router.message(F.from_user.id.in_(ADMIN_IDS))
async def admin_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle all admin messages (export or show menu)."""
    # Check if export button pressed (compared at runtime, not import time)
    if message.text and message.text == get_button("export_db"):
        buf, fits = build_export_zip()

        if buf is None:
            await message.answer(get_system("export_empty"))
            return

        if not fits:
            await message.answer(get_system("export_too_big"))
            return

        # Send ZIP file
        document = BufferedInputFile(
            file=buf.read(),
            filename="export.zip",
        )
        await message.answer_document(document)
        return

    # Any other message — show admin menu
    await message.answer(
        get_system("admin_menu"),
        reply_markup=admin_menu_keyboard(),
    )
