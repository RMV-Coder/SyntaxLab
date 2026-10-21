"""Typed API errors with stable, machine-readable codes."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An error that maps directly onto an HTTP response.

    `code` is part of the public contract; clients branch on it. `message` is for humans and
    must never contain stack traces or internal exception text.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers


class InvalidInput(ApiError):
    status_code = 422
    code = "invalid_input"


class EmptyText(InvalidInput):
    code = "empty_text"


class TextTooLong(InvalidInput):
    code = "text_too_long"


class TooManyWords(InvalidInput):
    code = "too_many_words"


class TooManySentences(InvalidInput):
    code = "too_many_sentences"


class InvalidGrammar(InvalidInput):
    code = "invalid_grammar"


class UnknownExercise(ApiError):
    status_code = 404
    code = "unknown_exercise"


class UnknownGrammar(ApiError):
    status_code = 404
    code = "unknown_grammar"


class UnsupportedLanguage(ApiError):
    status_code = 404
    code = "unsupported_language"


class UnknownScheme(ApiError):
    status_code = 404
    code = "unknown_scheme"


class UnsupportedStructure(ApiError):
    status_code = 422
    code = "unsupported_structure"


class ModelUnavailable(ApiError):
    status_code = 503
    code = "model_unavailable"


class Overloaded(ApiError):
    status_code = 503
    code = "overloaded"


class AnalysisTimeout(ApiError):
    status_code = 504
    code = "analysis_timeout"


class RateLimited(ApiError):
    status_code = 429
    code = "rate_limited"


class EngineFailure(ApiError):
    status_code = 500
    code = "engine_failure"


class InvalidEngineOutput(ApiError):
    """The engine produced a structure that fails validation. Never repaired silently."""

    status_code = 500
    code = "invalid_engine_output"
