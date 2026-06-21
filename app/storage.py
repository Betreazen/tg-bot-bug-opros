"""Filesystem storage: build answers + screenshots in a temp dir, then finalize.

Submissions are assembled in DATA_DIR/_tmp first and only moved into their final
location with an atomic rename. This guarantees a request folder is either fully
present or absent — never half-written if a download fails mid-way.
"""

import os
import shutil
import uuid
from pathlib import Path

from aiogram import Bot

from app.config import DATA_DIR
from app.phrases import get_question_label


TMP_DIR: Path = DATA_DIR / "_tmp"


def cleanup_tmp() -> None:
    """Remove leftover temp dirs from a previous crash. Safe at startup."""
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR, ignore_errors=True)


def _build_answers_text(
    answers: list[str],
    q4_text: str,
    screenshot_count: int,
) -> str:
    """Render answers.txt content."""
    lines: list[str] = []
    for i, answer in enumerate(answers, start=1):
        lines.append(f"Вопрос {i} ({get_question_label(i)}): {answer}")

    label_q4 = get_question_label(4)
    if q4_text and screenshot_count > 0:
        q4_line = f"{q4_text} (вложено скриншотов: {screenshot_count})"
    elif q4_text:
        q4_line = q4_text
    elif screenshot_count > 0:
        q4_line = f"(вложено скриншотов: {screenshot_count})"
    else:
        q4_line = "(пусто)"

    lines.append(f"Вопрос 4 ({label_q4}): {q4_line}")
    return "\n".join(lines)


async def build_submission(
    bot: Bot,
    answers: list[str],
    q4_text: str,
    q4_file_ids: list[tuple[str, str]],
) -> Path:
    """
    Download screenshots and write answers.txt into a fresh temp dir.

    Returns the temp dir path. Raises on any download/IO error (the caller is
    expected to discard the temp dir and keep the user's session intact so they
    can retry). The DB counter must NOT be touched before this succeeds.
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    staging = TMP_DIR / uuid.uuid4().hex
    staging.mkdir()

    try:
        for idx, (file_id, ext) in enumerate(q4_file_ids, start=1):
            file = await bot.get_file(file_id)
            dest = staging / f"screenshot_{idx}{ext}"
            await bot.download_file(file.file_path, destination=dest)

        text = _build_answers_text(answers, q4_text, len(q4_file_ids))
        (staging / "answers.txt").write_text(text, encoding="utf-8")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return staging


def finalize_submission(staging: Path, internal_id: int, request_no: int) -> None:
    """Atomically move a staged submission into its final request folder."""
    user_dir = DATA_DIR / str(internal_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    final = user_dir / f"request_{request_no}"
    # os.replace is atomic on the same filesystem; overwrite-safe if somehow exists.
    if final.exists():
        shutil.rmtree(final, ignore_errors=True)
    os.replace(staging, final)
