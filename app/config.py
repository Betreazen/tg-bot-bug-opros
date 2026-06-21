"""Bot configuration loaded from environment variables."""

import os
import sys
from pathlib import Path


def _require(name: str) -> str:
    """Read a required environment variable or exit with a clear message."""
    value = os.environ.get(name, "").strip()
    if not value:
        sys.stderr.write(
            f"[config] Обязательная переменная окружения {name} не задана. "
            f"Заполните её в .env (см. .env.example).\n"
        )
        raise SystemExit(1)
    return value


def _parse_admin_ids(raw: str) -> set[int]:
    """Parse comma-separated admin IDs, skipping malformed entries."""
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            sys.stderr.write(f"[config] Пропускаю некорректный ADMIN_IDS: {part!r}\n")
    return ids


BOT_TOKEN: str = _require("BOT_TOKEN")

ADMIN_IDS: set[int] = _parse_admin_ids(os.environ.get("ADMIN_IDS", ""))

TIMEOUT_SECONDS: int = int(os.environ.get("TIMEOUT_SECONDS", "600"))

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "/app/data"))

# Redis connection used for FSM persistence (sessions survive restarts).
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")

MAX_SCREENSHOTS: int = 5

# Per-file upload limit for a single screenshot.
MAX_SCREENSHOT_BYTES: int = int(
    os.environ.get("MAX_SCREENSHOT_BYTES", str(10 * 1024 * 1024))  # 10 MB
)

TELEGRAM_FILE_LIMIT: int = 50 * 1024 * 1024  # 50 MB

ALLOWED_IMAGE_MIMETYPES: set[str] = {"image/jpeg", "image/png"}
