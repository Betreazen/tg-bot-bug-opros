"""Filesystem storage: create folders, write answers.txt, save screenshots."""

from aiogram import Bot

from app.config import DATA_DIR
from app.phrases import get_question_label


async def save_submission(
    bot: Bot,
    internal_id: int,
    request_no: int,
    answers: list[str],
    q4_text: str,
    q4_file_ids: list[tuple[str, str]],
) -> None:
    """
    Save a completed submission to filesystem.

    Args:
        bot: Bot instance for downloading files.
        internal_id: User's internal numeric ID.
        request_no: Request number for this user.
        answers: List of text answers for Q1-Q3.
        q4_text: Combined text for Q4 (may be empty).
        q4_file_ids: List of (file_id, extension) for screenshots.
    """
    folder = DATA_DIR / str(internal_id) / f"request_{request_no}"
    folder.mkdir(parents=True, exist_ok=True)

    # Save screenshots
    for idx, (file_id, ext) in enumerate(q4_file_ids, start=1):
        file = await bot.get_file(file_id)
        dest = folder / f"screenshot_{idx}{ext}"
        await bot.download_file(file.file_path, destination=dest)

    # Build answers.txt
    lines: list[str] = []
    for i, answer in enumerate(answers, start=1):
        label = get_question_label(i)
        lines.append(f"Вопрос {i} ({label}): {answer}")

    # Q4 line
    label_q4 = get_question_label(4)
    screenshot_count = len(q4_file_ids)

    if q4_text and screenshot_count > 0:
        q4_line = f"{q4_text} (вложено скриншотов: {screenshot_count})"
    elif q4_text:
        q4_line = q4_text
    elif screenshot_count > 0:
        q4_line = f"(вложено скриншотов: {screenshot_count})"
    else:
        q4_line = "(пусто)"

    lines.append(f"Вопрос 4 ({label_q4}): {q4_line}")

    answers_file = folder / "answers.txt"
    answers_file.write_text("\n".join(lines), encoding="utf-8")
