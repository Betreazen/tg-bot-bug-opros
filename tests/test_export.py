"""Tests for ZIP export: empty case and exclusion of bot.db / _tmp."""

import zipfile

from app import export


def _make_data(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "DATA_DIR", tmp_path)
    return tmp_path


def test_empty_returns_none(tmp_path, monkeypatch):
    _make_data(tmp_path, monkeypatch)
    assert export.build_export_zip() == (None, False)


def test_excludes_db_and_tmp(tmp_path, monkeypatch):
    data = _make_data(tmp_path, monkeypatch)

    (data / "bot.db").write_text("db", encoding="utf-8")
    tmp = data / "_tmp"
    tmp.mkdir()
    (tmp / "junk.txt").write_text("junk", encoding="utf-8")
    req = data / "1" / "request_1"
    req.mkdir(parents=True)
    (req / "answers.txt").write_text("hello", encoding="utf-8")

    path, fits = export.build_export_zip()
    assert path is not None
    assert fits
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    finally:
        path.unlink(missing_ok=True)

    assert any("answers.txt" in n for n in names)
    assert not any("bot.db" in n for n in names)
    assert not any(n.startswith("_tmp") for n in names)
