"""Request/response models for the public v1 API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from syntaxlab_api.schemas.analysis import (
    Capability,
    Notice,
    Provenance,
    SentenceAnalysis,
    StructureKind,
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


# ---------------------------------------------------------------- languages


class LanguageStatus(StrEnum):
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


class SchemeInfo(_Model):
    id: str
    name: str
    url: str | None = None


class CapabilityInfo(_Model):
    capability: Capability
    scheme: SchemeInfo | None = None
    component: str


class SampleSentence(_Model):
    text: str
    note: str | None = None


class LanguageLimits(_Model):
    max_chars: int
    max_words: int
    max_sentences: int


class LanguageSummary(_Model):
    code: str
    name: str
    native_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    status: LanguageStatus
    capabilities: list[CapabilityInfo]
    structures: list[StructureKind] = Field(
        description="Structural analyses that can be requested for this language."
    )


class LanguageDetail(LanguageSummary):
    engine: str
    samples: list[SampleSentence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limits: LanguageLimits


class LanguageList(_Model):
    languages: list[LanguageSummary]


# ---------------------------------------------------------------- parse


class ParseRequest(_Model):
    language: str = Field(min_length=1, max_length=32, examples=["en"])
    text: str = Field(
        min_length=1,
        max_length=2000,  # hard transport cap; per-language limits are enforced after this
        examples=["I saw the man with a telescope."],
    )
    structures: list[StructureKind] | None = Field(
        default=None,
        description="Structural analyses to produce. Omit to get every structure the language "
        "supports. Requesting an unsupported structure is an error, never a fallback.",
    )


class LanguageRef(_Model):
    code: str
    name: str


class ParseResponse(_Model):
    language: LanguageRef
    text: str = Field(description="The analyzed text after Unicode NFC normalization.")
    sentences: list[SentenceAnalysis]
    provenance: Provenance
    notices: list[Notice] = Field(default_factory=list)


# ---------------------------------------------------------------- errors & health


class ErrorBody(_Model):
    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorResponse(_Model):
    error: ErrorBody


class HealthResponse(_Model):
    status: str


class ReadinessResponse(_Model):
    ready: bool
    languages: dict[str, LanguageStatus]
