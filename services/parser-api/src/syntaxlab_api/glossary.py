"""Curated explanations of annotation labels, one data file per annotation scheme.

Glossaries are keyed by *scheme*, not by language: every language whose engine follows UD v2
automatically gets the UD explanations. Language-specific caveats (e.g. what ``nsubj`` means
for the Tagalog ang-phrase) go in an entry's ``language_notes``. Adding a scheme or a note is a
data change in ``data/glossary/<scheme-id>.yaml``; no code changes.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from syntaxlab_api.languages.config import ConfigError, SchemeConfig

logger = logging.getLogger(__name__)

_SCHEME_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )


class PosFamily(StrEnum):
    """Coarse grouping of POS tags, used for consistent colouring across schemes."""

    NOMINAL = "nominal"
    VERBAL = "verbal"
    MODIFIER = "modifier"
    FUNCTION = "function"
    OTHER = "other"


class GlossaryValue(_Model):
    name: str
    gloss: str | None = Field(default=None, description="Leipzig-style gloss abbreviation.")
    gloss_standard: bool = Field(
        default=True,
        description="False if the abbreviation is not in the Leipzig Glossing Rules list.",
    )


class GlossaryEntry(_Model):
    name: str
    definition: str
    url: str | None = None
    textbook: str | None = Field(
        default=None, description="Closest category in introductory textbooks (reading aid only)."
    )
    family: PosFamily | None = None
    values: dict[str, GlossaryValue] = Field(default_factory=dict)
    language_notes: dict[str, str] = Field(default_factory=dict)


class GlossaryFile(_Model):
    id: str
    kind: str
    source: str | None = None
    entries: dict[str, GlossaryEntry]


class Glossary(_Model):
    id: str
    name: str
    url: str | None = None
    kind: str
    source: str | None = None
    entries: dict[str, GlossaryEntry]


def load_glossaries(directory: Path, schemes: Mapping[str, SchemeConfig]) -> dict[str, Glossary]:
    """Load and validate the glossary of every declared scheme. Missing files are allowed
    (the UI then says no curated definition exists); malformed files fail startup."""
    glossaries: dict[str, Glossary] = {}
    for scheme_id, scheme in schemes.items():
        if not _SCHEME_ID.match(scheme_id):
            raise ConfigError(f"invalid scheme id {scheme_id!r}")
        path = directory / f"{scheme_id}.yaml"
        if not path.is_file():
            logger.warning("no glossary for scheme %s (%s)", scheme_id, path)
            continue
        try:
            data = GlossaryFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValidationError) as exc:
            raise ConfigError(f"invalid glossary {path}: {exc}") from exc
        if data.id != scheme_id:
            raise ConfigError(f"glossary {path} declares id {data.id!r}, expected {scheme_id!r}")
        glossaries[scheme_id] = Glossary(
            id=scheme_id,
            name=scheme.name,
            url=scheme.url,
            kind=data.kind,
            source=data.source,
            entries=data.entries,
        )
    return glossaries
