"""Admin handlers: admin menu and database export."""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext

from app.config import ADMIN_IDS
from app.phrases import get_system, get_button
from app.keyboards import admin_menu_keyboard
from app.export import build_export_zip

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.from_user.id.in_(ADMIN_IDS))
async def admin_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle all admin messages (export or show menu)."""
    # Check if export button pressed (compared at runtime, not import time)
    if message.text and message.text == get_button("export_db"):
        try:
            # ZIP building is blocking IO — run it off the event loop.
            zip_path, fits = await asyncio.to_thread(build_export_zip)
        except Exception:
            logger.exception("Export failed")
            await message.answer(get_system("save_failed"))
            return

        if zip_path is None:
            await message.answer(get_system("export_empty"))
            return

        try:
            if not fits:
                await message.answer(get_system("export_too_big"))
                return
            await message.answer_document(FSInputFile(zip_path, filename="export.zip"))
        finally:
            zip_path.unlink(missing_ok=True)
        return

    # Any other message — show admin menu
    await message.answer(
        get_system("admin_menu"),
        reply_markup=admin_menu_keyboard(),
    )
