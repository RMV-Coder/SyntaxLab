"""User text normalization and validation (before any engine sees it)."""

from __future__ import annotations

import unicodedata

from syntaxlab_api import errors
from syntaxlab_api.languages.runtime import Limits

_ALLOWED_CONTROL = {"\t", "\n", "\r"}
# Bidirectional embedding/override/isolate controls can make rendered text differ from its
# logical order (the "Trojan Source" class of spoofing); they have no place in a sentence to parse.
_BIDI_CONTROLS = {chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))}


def normalize_text(raw: str, limits: Limits) -> str:
    """Return NFC-normalized, trimmed text or raise a typed ``InvalidInput`` error."""
    text = unicodedata.normalize("NFC", raw).strip()
    if not text:
        raise errors.EmptyText("Enter a sentence to analyze.")
    for ch in text:
        category = unicodedata.category(ch)
        if (category == "Cc" and ch not in _ALLOWED_CONTROL) or category == "Cs":
            raise errors.InvalidInput(
                "The text contains control characters.", details={"codepoint": f"U+{ord(ch):04X}"}
            )
        if ch in _BIDI_CONTROLS:
            raise errors.InvalidInput(
                "The text contains bidirectional control characters.",
                details={"codepoint": f"U+{ord(ch):04X}"},
            )
    if len(text) > limits.max_chars:
        raise errors.TextTooLong(
            f"The text is {len(text)} characters long; the limit is {limits.max_chars}.",
            details={"length": len(text), "max_chars": limits.max_chars},
        )
    # Cheap pre-check: an engine never produces fewer words than whitespace-separated chunks.
    chunks = len(text.split())
    if chunks > limits.max_words:
        raise errors.TooManyWords(
            f"The text has at least {chunks} words; the limit is {limits.max_words}.",
            details={"words": chunks, "max_words": limits.max_words},
        )
    return text


def check_analysis_size(sentence_count: int, word_count: int, limits: Limits) -> None:
    """Exact post-analysis limits (the engine decides what a sentence and a word are)."""
    if sentence_count > limits.max_sentences:
        raise errors.TooManySentences(
            f"Found {sentence_count} sentences; analyze up to {limits.max_sentences} at a time.",
            details={"sentences": sentence_count, "max_sentences": limits.max_sentences},
        )
    if word_count > limits.max_words:
        raise errors.TooManyWords(
            f"The text has {word_count} words; the limit is {limits.max_words}.",
            details={"words": word_count, "max_words": limits.max_words},
        )
