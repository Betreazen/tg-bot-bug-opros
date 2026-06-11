"""Bot configuration loaded from environment variables."""

import os
from pathlib import Path


BOT_TOKEN: str = os.environ["BOT_TOKEN"]

ADMIN_IDS: set[int] = {
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip()
}

TIMEOUT_SECONDS: int = int(os.environ.get("TIMEOUT_SECONDS", "600"))

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "/app/data"))

MAX_SCREENSHOTS: int = 5

TELEGRAM_FILE_LIMIT: int = 50 * 1024 * 1024  # 50 MB

ALLOWED_IMAGE_MIMETYPES: set[str] = {"image/jpeg", "image/png"}
