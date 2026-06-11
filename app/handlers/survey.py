"""Survey handlers: step-by-step Q1-Q4, media group logic, timeout, saving."""

import asyncio
from typing import Any

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import ADMIN_IDS, TIMEOUT_SECONDS, MAX_SCREENSHOTS, ALLOWED_IMAGE_MIMETYPES
from app.states import SurveyStates
from app.phrases import get_system, get_question_text, get_button
from app.keyboards import finish_keyboard, confirm_empty_keyboard, remove_keyboard
from app.db import complete_submission
from app.storage import save_submission

router = Router()

# ─── Timeout management ──────────────────────────────────────────────

_timeout_tasks: dict[int, asyncio.Task] = {}


async def _timeout_callback(user_id: int, state: FSMContext, bot: Bot, chat_id: int) -> None:
    """Fires after TIMEOUT_SECONDS of inactivity."""
    await asyncio.sleep(TIMEOUT_SECONDS)
    # Session expired
    await state.clear()
    _timeout_tasks.pop(user_id, None)
    timeout_min = TIMEOUT_SECONDS // 60
    try:
        await bot.send_message(
            chat_id,
            get_system("timeout", timeout_min=timeout_min),
            reply_markup=remove_keyboard(),
        )
    except Exception:
        pass


def _reset_timeout(user_id: int, state: FSMContext, bot: Bot, chat_id: int) -> None:
    """Cancel existing timeout and start a new one (sliding window)."""
    task = _timeout_tasks.pop(user_id, None)
    if task is not None:
        task.cancel()
    _timeout_tasks[user_id] = asyncio.create_task(
        _timeout_callback(user_id, state, bot, chat_id)
    )


def _cancel_timeout(user_id: int) -> None:
    """Cancel timeout for user (on survey completion or /start reset)."""
    task = _timeout_tasks.pop(user_id, None)
    if task is not None:
        task.cancel()


# ─── Helpers ─────────────────────────────────────────────────────────

def _is_forwarded(message: Message) -> bool:
    """Check if message is forwarded."""
    return message.forward_origin is not None or message.forward_date is not None


def _get_image_ext(mime_type: str | None) -> str:
    """Map MIME type to file extension."""
    if mime_type == "image/png":
        return ".png"
    return ".jpg"


# ─── Q1-Q3: Text questions ───────────────────────────────────────────

async def _handle_text_question(
    message: Message, state: FSMContext, bot: Bot, question_num: int
) -> None:
    """Generic handler for text-only questions Q1-Q3."""
    user_id = message.from_user.id
    _reset_timeout(user_id, state, bot, message.chat.id)

    # Reject forwarded messages
    if _is_forwarded(message):
        await message.answer(get_system("forwarded_rejected"))
        return

    # Must be text content
    if not message.text:
        await message.answer(get_system("text_expected"))
        return

    # Must not be empty
    text = message.text.strip()
    if not text:
        await message.answer(get_system("empty_answer"))
        return

    # Save answer and advance
    data = await state.get_data()
    answers: list[str] = data.get("answers", [])
    answers.append(text)
    await state.update_data(answers=answers)

    # Move to next question
    next_q = question_num + 1
    if next_q <= 3:
        next_state = [SurveyStates.q1, SurveyStates.q2, SurveyStates.q3][next_q - 1]
        await state.set_state(next_state)
        await message.answer(get_question_text(next_q))
    else:
        # Move to Q4
        await state.set_state(SurveyStates.q4)
        await message.answer(
            get_question_text(4),
            reply_markup=finish_keyboard(),
        )


@router.message(SurveyStates.q1)
async def handle_q1(message: Message, state: FSMContext, bot: Bot) -> None:
    await _handle_text_question(message, state, bot, 1)


@router.message(SurveyStates.q2)
async def handle_q2(message: Message, state: FSMContext, bot: Bot) -> None:
    await _handle_text_question(message, state, bot, 2)


@router.message(SurveyStates.q3)
async def handle_q3(message: Message, state: FSMContext, bot: Bot) -> None:
    await _handle_text_question(message, state, bot, 3)


# ─── Q4: Media + text + finish ───────────────────────────────────────

@router.message(SurveyStates.q4)
async def handle_q4(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle Q4 input: text, photos, documents, or finish button."""
    user_id = message.from_user.id
    _reset_timeout(user_id, state, bot, message.chat.id)

    # Reject forwarded messages
    if _is_forwarded(message):
        await message.answer(get_system("forwarded_rejected"))
        return

    # Check if user pressed "Finish" button
    if message.text and message.text == get_button("finish"):
        await _handle_finish(message, state, bot)
        return

    data = await state.get_data()
    q4_texts: list[str] = data.get("q4_texts", [])
    q4_files: list[tuple[str, str]] = data.get("q4_files", [])
    media_group_processed: set = data.get("media_group_processed", set())

    # ── Handle photo (compressed by Telegram) ──
    if message.photo:
        # Check screenshot limit
        if len(q4_files) >= MAX_SCREENSHOTS:
            await message.answer(get_system("q4_max_screenshots"))
            return

        # Handle media group (album) deduplication
        if message.media_group_id:
            if message.media_group_id in media_group_processed:
                # Already handling this group, just save photo
                pass
            else:
                media_group_processed.add(message.media_group_id)

        # Get largest photo
        photo = message.photo[-1]
        file_id = photo.file_id
        ext = ".jpg"  # Telegram photos are always JPEG

        if len(q4_files) < MAX_SCREENSHOTS:
            q4_files.append((file_id, ext))

        # Capture caption as text
        if message.caption and message.caption.strip():
            q4_texts.append(message.caption.strip())

        await state.update_data(
            q4_files=q4_files,
            q4_texts=q4_texts,
            media_group_processed=media_group_processed,
        )
        return

    # ── Handle document (check if it's an image) ──
    if message.document:
        mime = message.document.mime_type
        if mime not in ALLOWED_IMAGE_MIMETYPES:
            await message.answer(get_system("q4_only_images"))
            return

        # Check screenshot limit
        if len(q4_files) >= MAX_SCREENSHOTS:
            await message.answer(get_system("q4_max_screenshots"))
            return

        # Handle media group
        if message.media_group_id:
            if message.media_group_id in media_group_processed:
                pass
            else:
                media_group_processed.add(message.media_group_id)

        file_id = message.document.file_id
        ext = _get_image_ext(mime)

        q4_files.append((file_id, ext))

        # Capture caption
        if message.caption and message.caption.strip():
            q4_texts.append(message.caption.strip())

        await state.update_data(
            q4_files=q4_files,
            q4_texts=q4_texts,
            media_group_processed=media_group_processed,
        )
        return

    # ── Handle plain text ──
    if message.text:
        text = message.text.strip()
        if text:
            q4_texts.append(text)
            await state.update_data(q4_texts=q4_texts)
        return

    # ── Anything else (video, voice, sticker, etc.) — reject ──
    await message.answer(get_system("q4_only_images"))


async def _handle_finish(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle finish button press in Q4."""
    data = await state.get_data()
    q4_texts: list[str] = data.get("q4_texts", [])
    q4_files: list[tuple[str, str]] = data.get("q4_files", [])

    # If Q4 is completely empty — ask for confirmation
    if not q4_texts and not q4_files:
        await state.set_state(SurveyStates.q4_confirm_empty)
        await message.answer(
            get_system("q4_confirm_empty"),
            reply_markup=confirm_empty_keyboard(),
        )
        return

    # Save submission
    await _complete_and_save(message, state, bot)


# ─── Q4 empty confirmation ───────────────────────────────────────────

@router.callback_query(SurveyStates.q4_confirm_empty, F.data == "confirm_empty_yes")
async def confirm_empty_yes(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """User confirmed finishing with empty Q4."""
    _reset_timeout(callback.from_user.id, state, bot, callback.message.chat.id)
    await callback.answer()
    await callback.message.delete()
    await _complete_and_save(callback.message, state, bot)


@router.callback_query(SurveyStates.q4_confirm_empty, F.data == "confirm_empty_back")
async def confirm_empty_back(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """User chose to go back to Q4."""
    _reset_timeout(callback.from_user.id, state, bot, callback.message.chat.id)
    await callback.answer()
    await callback.message.delete()
    await state.set_state(SurveyStates.q4)
    await callback.message.answer(
        get_question_text(4),
        reply_markup=finish_keyboard(),
    )


# ─── Completion ──────────────────────────────────────────────────────

async def _complete_and_save(message: Message, state: FSMContext, bot: Bot) -> None:
    """Finalize submission: save to DB and filesystem."""
    data = await state.get_data()
    answers: list[str] = data.get("answers", [])
    q4_texts: list[str] = data.get("q4_texts", [])
    q4_files: list[tuple[str, str]] = data.get("q4_files", [])

    telegram_id = message.chat.id

    # Cancel timeout
    _cancel_timeout(telegram_id)

    # Atomically get/create internal_id and request_no
    internal_id, request_no = await complete_submission(telegram_id)

    # Combined Q4 text (multiple messages joined by newline)
    q4_text_combined = "\n".join(q4_texts) if q4_texts else ""

    # Save to filesystem
    await save_submission(
        bot=bot,
        internal_id=internal_id,
        request_no=request_no,
        answers=answers,
        q4_text=q4_text_combined,
        q4_file_ids=q4_files,
    )

    # Clear state
    await state.clear()

    # Confirm to user
    await message.answer(
        get_system("submission_saved", n=request_no),
        reply_markup=remove_keyboard(),
    )
