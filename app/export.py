"""ZIP export of the submissions folder tree."""

import zipfile
from pathlib import Path
from io import BytesIO

from app.config import DATA_DIR, TELEGRAM_FILE_LIMIT


def build_export_zip() -> tuple[BytesIO | None, bool]:
    """
    Build a ZIP archive of all submission folders.

    Returns:
        (buffer, fits) — buffer with ZIP data and whether it fits Telegram's 50MB limit.
        If data directory has no submission folders, returns (None, False).
    """
    buf = BytesIO()
    has_content = False

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(DATA_DIR.rglob("*")):
            # Skip bot.db and non-files
            if path.name == "bot.db":
                continue
            if not path.is_file():
                continue
            # Relative path inside ZIP
            rel = path.relative_to(DATA_DIR)
            zf.write(path, arcname=str(rel))
            has_content = True

    if not has_content:
        return None, False

    size = buf.tell()
    buf.seek(0)
    return buf, size <= TELEGRAM_FILE_LIMIT
