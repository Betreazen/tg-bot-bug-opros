"""ZIP export of the submissions folder tree."""

import tempfile
import zipfile
from pathlib import Path

from app.config import DATA_DIR, TELEGRAM_FILE_LIMIT


def build_export_zip() -> tuple[Path | None, bool]:
    """
    Build a ZIP archive of all submission folders on disk.

    Synchronous and IO-heavy — call via asyncio.to_thread so it doesn't block
    the event loop.

    Returns:
        (path, fits) — path to a temp ZIP file and whether it fits Telegram's
        50MB limit. If there are no submissions, returns (None, False). The
        caller owns the temp file and must delete it.
    """
    tmp = tempfile.NamedTemporaryFile(prefix="export_", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    has_content = False
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(DATA_DIR.rglob("*")):
                # Skip bot.db, the temp staging area, and non-files.
                if path.name == "bot.db":
                    continue
                if not path.is_file():
                    continue
                try:
                    rel = path.relative_to(DATA_DIR)
                except ValueError:
                    continue
                if rel.parts and rel.parts[0] == "_tmp":
                    continue
                zf.write(path, arcname=str(rel))
                has_content = True
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    if not has_content:
        tmp_path.unlink(missing_ok=True)
        return None, False

    fits = tmp_path.stat().st_size <= TELEGRAM_FILE_LIMIT
    return tmp_path, fits
