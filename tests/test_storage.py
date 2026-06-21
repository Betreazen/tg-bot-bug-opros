"""Tests for filesystem storage: staging, atomic finalize, answers rendering."""

from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from app import storage


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "TMP_DIR", tmp_path / "_tmp")
    return tmp_path


def _bot_that_downloads():
    async def fake_download(file_path, destination):
        Path(destination).write_bytes(b"img-bytes")

    return SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_path="remote/path")),
        download_file=AsyncMock(side_effect=fake_download),
    )


# ─── _build_answers_text ─────────────────────────────────────────────

def test_answers_text_with_text_and_screenshots():
    out = storage._build_answers_text(["a", "b", "c"], "broken login", 2)
    assert "Вопрос 1" in out and "a" in out
    assert "broken login (вложено скриншотов: 2)" in out


def test_answers_text_screens_only():
    out = storage._build_answers_text(["a", "b", "c"], "", 3)
    assert "(вложено скриншотов: 3)" in out


def test_answers_text_empty_q4():
    out = storage._build_answers_text(["a", "b", "c"], "", 0)
    assert "(пусто)" in out


# ─── build_submission ────────────────────────────────────────────────

async def test_build_submission_writes_files(tmp_storage):
    bot = _bot_that_downloads()
    staging = await storage.build_submission(
        bot=bot,
        answers=["x", "y", "z"],
        q4_text="note",
        q4_file_ids=[("f1", ".jpg"), ("f2", ".png")],
    )
    assert (staging / "answers.txt").exists()
    assert (staging / "screenshot_1.jpg").exists()
    assert (staging / "screenshot_2.png").exists()
    assert bot.download_file.await_count == 2


async def test_build_submission_cleans_up_on_failure(tmp_storage):
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_path="p")),
        download_file=AsyncMock(side_effect=RuntimeError("network")),
    )
    with pytest.raises(RuntimeError):
        await storage.build_submission(
            bot=bot, answers=["x"], q4_text="", q4_file_ids=[("f1", ".jpg")]
        )
    # No staging dir should be left behind.
    leftovers = list((tmp_storage / "_tmp").glob("*")) if (tmp_storage / "_tmp").exists() else []
    assert leftovers == []


# ─── finalize_submission ─────────────────────────────────────────────

def test_finalize_moves_into_place(tmp_storage):
    staging = tmp_storage / "_tmp" / "abc"
    staging.mkdir(parents=True)
    (staging / "answers.txt").write_text("hi", encoding="utf-8")

    storage.finalize_submission(staging, internal_id=7, request_no=3)

    final = tmp_storage / "7" / "request_3"
    assert (final / "answers.txt").read_text(encoding="utf-8") == "hi"
    assert not staging.exists()


def test_finalize_overwrites_existing(tmp_storage):
    final = tmp_storage / "7" / "request_3"
    final.mkdir(parents=True)
    (final / "stale.txt").write_text("old", encoding="utf-8")

    staging = tmp_storage / "_tmp" / "abc"
    staging.mkdir(parents=True)
    (staging / "answers.txt").write_text("new", encoding="utf-8")

    storage.finalize_submission(staging, internal_id=7, request_no=3)

    assert (final / "answers.txt").exists()
    assert not (final / "stale.txt").exists()


# ─── cleanup_tmp ─────────────────────────────────────────────────────

def test_cleanup_tmp(tmp_storage):
    tmp = tmp_storage / "_tmp"
    tmp.mkdir()
    (tmp / "leftover").write_text("x", encoding="utf-8")
    storage.cleanup_tmp()
    assert not tmp.exists()
