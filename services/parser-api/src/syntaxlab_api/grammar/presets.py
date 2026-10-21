"""Preset grammars for the Algorithm Lab (``data/grammars/*.yaml``).

Each example sentence declares the expected outcome, and the test-suite runs every example
through the parser, so a preset can never claim behaviour the algorithm does not produce.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from syntaxlab_api.grammar.grammar import compile_grammar
from syntaxlab_api.languages.config import ConfigError


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )


class ExpectedOutcome(_Model):
    accepted: bool
    parses: int = Field(ge=0)


class GrammarExample(_Model):
    text: str = Field(min_length=1)
    note: str | None = None
    expect: ExpectedOutcome


class GrammarPreset(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    order: int = Field(default=100, description="Position in the preset list (ascending).")
    name: str
    description: str
    grammar: str
    examples: list[GrammarExample] = Field(default_factory=list)


def load_presets(directory: Path) -> dict[str, GrammarPreset]:
    presets: dict[str, GrammarPreset] = {}
    for path in sorted(directory.glob("*.yaml")):
        try:
            preset = GrammarPreset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValidationError) as exc:
            raise ConfigError(f"invalid grammar preset {path}: {exc}") from exc
        if preset.id != path.stem:
            raise ConfigError(f"grammar preset {path} declares id {preset.id!r}")
        grammar, problems = compile_grammar(preset.grammar)
        if grammar is None:
            raise ConfigError(
                f"grammar preset {preset.id!r} does not compile: "
                + "; ".join(p.message for p in problems)
            )
        presets[preset.id] = preset
    return dict(sorted(presets.items(), key=lambda kv: (kv[1].order, kv[0])))
