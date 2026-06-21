"""Tests for config parsing helpers."""

from app.config import _parse_admin_ids


def test_parse_admin_ids_valid():
    assert _parse_admin_ids("1, 2 ,3") == {1, 2, 3}


def test_parse_admin_ids_skips_malformed():
    assert _parse_admin_ids("1,x, ,3,") == {1, 3}


def test_parse_admin_ids_empty():
    assert _parse_admin_ids("") == set()
    assert _parse_admin_ids("   ") == set()
