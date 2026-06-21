"""Shared test setup: provide required env vars before app modules import."""

import os

# app.config reads these at import time — set them before any test imports it.
os.environ.setdefault("BOT_TOKEN", "12345:test-token")
os.environ.setdefault("ADMIN_IDS", "1,2")
os.environ.setdefault("DATA_DIR", "./_test_data")
