"""Language configuration file (``config/languages.yaml``).

This file is the *only* place a language is declared. Each entry names an engine (see
``syntaxlab_api.engines.registry``), the engine's options, the annotation scheme of each layer,
and user-facing metadata (samples, notes, limits).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from syntaxlab_api.schemas.analysis import Capability


class ConfigError(ValueError):
    """The language configuration file is invalid."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SchemeConfig(_Model):
    name: str
    url: str | None = None


class LimitsConfig(_Model):
    max_chars: int | None = Field(default=None, ge=1, le=2000)
    max_words: int | None = Field(default=None, ge=1, le=500)
    max_sentences: int | None = Field(default=None, ge=1, le=20)


class SampleConfig(_Model):
    text: str = Field(min_length=1)
    note: str | None = None


class LanguageConfig(_Model):
    code: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
    name: str = Field(min_length=1)
    native_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    enabled: bool = True
    engine: str = Field(min_length=1, description="Entry-point name or 'module:Class'.")
    engine_options: dict[str, Any] = Field(default_factory=dict)
    schemes: dict[Capability, str] = Field(
        default_factory=dict, description="Annotation scheme id per capability."
    )
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    samples: list[SampleConfig] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("aliases")
    @classmethod
    def _lowercase_aliases(cls, value: list[str]) -> list[str]:
        return [a.lower() for a in value]


class LanguagesFile(_Model):
    schemes: dict[str, SchemeConfig] = Field(default_factory=dict)
    languages: list[LanguageConfig]

    @model_validator(mode="after")
    def _check_references(self) -> LanguagesFile:
        seen: dict[str, str] = {}
        for lang in self.languages:
            for key in (lang.code.lower(), *lang.aliases):
                if key in seen:
                    raise ValueError(
                        f"language code/alias {key!r} is used by both {seen[key]!r} and "
                        f"{lang.code!r}"
                    )
                seen[key] = lang.code
            for capability, scheme in lang.schemes.items():
                if scheme not in self.schemes:
                    raise ValueError(
                        f"language {lang.code!r}: {capability.value} scheme {scheme!r} is not "
                        "declared under 'schemes'"
                    )
        return self


def load_languages_file(path: Path) -> LanguagesFile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"language configuration not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"language configuration is not valid YAML: {exc}") from exc
    try:
        return LanguagesFile.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid language configuration {path}:\n{exc}") from exc
