"""Keyboard builders for the bot."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from app.phrases import get_button


def finish_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with 'Finish' button for Q4."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_button("finish"))]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def confirm_empty_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for confirming empty Q4."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_button("confirm_empty_yes"),
                    callback_data="confirm_empty_yes",
                ),
                InlineKeyboardButton(
                    text=get_button("confirm_empty_back"),
                    callback_data="confirm_empty_back",
                ),
            ]
        ]
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with admin menu."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_button("export_db"))]],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Remove any reply keyboard."""
    return ReplyKeyboardRemove()
