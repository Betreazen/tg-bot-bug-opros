"""Tests for the phrases loader (uses the real phrases.json)."""

from app import phrases


def setup_module(module):
    phrases.load_phrases()  # default path = project-root phrases.json


def test_questions_present():
    for n in range(1, 5):
        assert phrases.get_question_text(n)
        assert phrases.get_question_label(n)


def test_buttons():
    assert phrases.get_button("finish") == "Завершить"


def test_system_substitution():
    msg = phrases.get_system("submission_saved", n=7)
    assert "7" in msg


def test_new_phrases_exist():
    # Added during the hardening work — must be present.
    assert phrases.get_system("save_failed")
    assert phrases.get_system("q4_file_too_big")
