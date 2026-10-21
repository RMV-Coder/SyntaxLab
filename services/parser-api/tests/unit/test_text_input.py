from __future__ import annotations

import pytest

from syntaxlab_api import errors
from syntaxlab_api.analysis.text_input import check_analysis_size, normalize_text
from syntaxlab_api.languages.runtime import Limits

LIMITS = Limits(max_chars=40, max_words=5, max_sentences=1)


def test_nfc_normalization_and_trimming() -> None:
    decomposed = "  Cafe\u0301 au lait.  "  # e + COMBINING ACUTE ACCENT
    assert normalize_text(decomposed, LIMITS) == "Caf\u00e9 au lait."


@pytest.mark.parametrize(
    "text", ["Kumakain ng kanin ang bata.", "Ñoño señor.", "日本語の文。", "Naïve 🙂."]
)
def test_unicode_text_accepted(text: str) -> None:
    assert normalize_text(text, LIMITS) == text


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty(text: str) -> None:
    with pytest.raises(errors.EmptyText):
        normalize_text(text, LIMITS)


@pytest.mark.parametrize("bad", ["\x00", "\x07", "\x1b", "\ud800"])
def test_control_and_surrogate_characters_rejected(bad: str) -> None:
    with pytest.raises(errors.InvalidInput, match="control"):
        normalize_text(f"a{bad}b", LIMITS)


@pytest.mark.parametrize("bidi", ["‮", "⁦", "⁩"])
def test_bidi_controls_rejected(bidi: str) -> None:
    with pytest.raises(errors.InvalidInput, match="bidirectional"):
        normalize_text(f"abc{bidi}def", LIMITS)


def test_tabs_and_newlines_allowed() -> None:
    assert normalize_text("a\tb\nc", LIMITS) == "a\tb\nc"


def test_too_long() -> None:
    with pytest.raises(errors.TextTooLong) as info:
        normalize_text("x" * 41, LIMITS)
    assert info.value.details == {"length": 41, "max_chars": 40}


def test_too_many_whitespace_words() -> None:
    with pytest.raises(errors.TooManyWords):
        normalize_text("a b c d e f", LIMITS)


def test_post_analysis_limits() -> None:
    check_analysis_size(1, 5, LIMITS)
    with pytest.raises(errors.TooManySentences):
        check_analysis_size(2, 4, LIMITS)
    with pytest.raises(errors.TooManyWords):
        check_analysis_size(1, 6, LIMITS)
