"""Survey handlers: step-by-step Q1-Q4, album handling, timeout, saving."""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import (
    MAX_SCREENSHOTS,
    MAX_SCREENSHOT_BYTES,
    ALLOWED_IMAGE_MIMETYPES,
)
from app.states import SurveyStates
from app.phrases import get_system, get_question_text, get_button
from app.keyboards import finish_keyboard, confirm_empty_keyboard, remove_keyboard
from app.db import complete_submission
from app.storage import build_submission, finalize_submission
from app import timeouts

logger = logging.getLogger(__name__)

router = Router()

# Per-user lock: serializes state read-modify-write so concurrent album photos
# (Telegram delivers each as a separate, concurrently-handled message) can't
# clobber each other's q4_files entries.
_user_locks: dict[int, asyncio.Lock] = {}


def _get_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def release_lock(user_id: int) -> None:
    """Drop a user's lock at session end (best-effort, skips a held lock)."""
    lock = _user_locks.get(user_id)
    if lock is not None and not lock.locked():
        _user_locks.pop(user_id, None)


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
    await timeouts.touch(message.chat.id)

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
        next_state = getattr(SurveyStates, f"q{next_q}")
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
    await timeouts.touch(message.chat.id)

    # Reject forwarded messages
    if _is_forwarded(message):
        await message.answer(get_system("forwarded_rejected"))
        return

    # Check if user pressed "Finish" button
    if message.text and message.text == get_button("finish"):
        await _handle_finish(message, state, bot)
        return

    # Serialize state mutations so album photos don't race each other.
    async with _get_lock(message.from_user.id):
        data = await state.get_data()
        q4_texts: list[str] = data.get("q4_texts", [])
        q4_files: list = data.get("q4_files", [])
        limit_warned: bool = data.get("q4_limit_warned", False)

        # ── Handle photo (compressed by Telegram) or image document ──
        new_file: tuple[str, str] | None = None

        if message.photo:
            photo = message.photo[-1]
            if photo.file_size and photo.file_size > MAX_SCREENSHOT_BYTES:
                await message.answer(get_system("q4_file_too_big"))
                return
            new_file = (photo.file_id, ".jpg")  # Telegram photos are always JPEG

        elif message.document:
            mime = message.document.mime_type
            if mime not in ALLOWED_IMAGE_MIMETYPES:
                await message.answer(get_system("q4_only_images"))
                return
            if message.document.file_size and message.document.file_size > MAX_SCREENSHOT_BYTES:
                await message.answer(get_system("q4_file_too_big"))
                return
            new_file = (message.document.file_id, _get_image_ext(mime))

        if new_file is not None:
            if len(q4_files) >= MAX_SCREENSHOTS:
                # Warn only once per session to avoid spamming on big albums.
                if not limit_warned:
                    await message.answer(get_system("q4_max_screenshots"))
                    await state.update_data(q4_limit_warned=True)
                return

            q4_files.append(list(new_file))
            if message.caption and message.caption.strip():
                q4_texts.append(message.caption.strip())

            await state.update_data(q4_files=q4_files, q4_texts=q4_texts)
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
    q4_files: list = data.get("q4_files", [])

    # If Q4 is completely empty — ask for confirmation
    if not q4_texts and not q4_files:
        await state.set_state(SurveyStates.q4_confirm_empty)
        await message.answer(
            get_system("q4_confirm_empty"),
            reply_markup=confirm_empty_keyboard(),
        )
        return

    # Save submission
    await _complete_and_save(message.chat.id, state, bot)


# ─── Q4 empty confirmation ───────────────────────────────────────────

@router.callback_query(SurveyStates.q4_confirm_empty, F.data == "confirm_empty_yes")
async def confirm_empty_yes(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """User confirmed finishing with empty Q4."""
    await timeouts.touch(callback.message.chat.id)
    await callback.answer()
    await callback.message.delete()
    await _complete_and_save(callback.message.chat.id, state, bot)


@router.callback_query(SurveyStates.q4_confirm_empty, F.data == "confirm_empty_back")
async def confirm_empty_back(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """User chose to go back to Q4."""
    await timeouts.touch(callback.message.chat.id)
    await callback.answer()
    await callback.message.delete()
    await state.set_state(SurveyStates.q4)
    await callback.message.answer(
        get_question_text(4),
        reply_markup=finish_keyboard(),
    )


# ─── Completion ──────────────────────────────────────────────────────

async def _complete_and_save(chat_id: int, state: FSMContext, bot: Bot) -> None:
    """Finalize submission: download files, then commit DB + filesystem atomically."""
    data = await state.get_data()
    answers: list[str] = data.get("answers", [])
    q4_texts: list[str] = data.get("q4_texts", [])
    q4_files_raw: list = data.get("q4_files", [])
    q4_files: list[tuple[str, str]] = [tuple(f) for f in q4_files_raw]

    q4_text_combined = "\n".join(q4_texts) if q4_texts else ""

    # 1. Stage everything to a temp dir (download screenshots, write answers.txt).
    #    On failure: nothing was committed — keep the session so the user retries.
    try:
        staging = await build_submission(
            bot=bot,
            answers=answers,
            q4_text=q4_text_combined,
            q4_file_ids=q4_files,
        )
    except Exception:
        logger.exception("Failed to stage submission for chat %s", chat_id)
        await bot.send_message(chat_id, get_system("save_failed"))
        return

    # 2. Allocate ids and atomically move the staged folder into place.
    try:
        internal_id, request_no = await complete_submission(chat_id)
        finalize_submission(staging, internal_id, request_no)
    except Exception:
        logger.exception("Failed to finalize submission for chat %s", chat_id)
        await bot.send_message(chat_id, get_system("save_failed"))
        return

    # Success — tear down session and timeout.
    await timeouts.cancel(chat_id)
    await state.clear()
    release_lock(chat_id)

    logger.info("Submission saved: internal_id=%s request_no=%s", internal_id, request_no)
    await bot.send_message(
        chat_id,
        get_system("submission_saved", n=request_no),
        reply_markup=remove_keyboard(),
    )
