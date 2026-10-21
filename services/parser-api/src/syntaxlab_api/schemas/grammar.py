"""Request/response models for the Algorithm Lab (formal grammars and the Earley parser)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from syntaxlab_api.grammar.presets import GrammarExample


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class GrammarSymbol(_Model):
    kind: Literal["nonterminal", "terminal"]
    value: str


class GrammarRule(_Model):
    index: int = Field(description="0 is the augmented rule γ → start added by the parser.")
    lhs: str
    rhs: list[GrammarSymbol]
    text: str
    line: int | None


class GrammarDiagnostic(_Model):
    severity: Literal["error", "warning"]
    code: str
    message: str
    line: int | None


class GrammarSummary(_Model):
    start: str
    rules: list[GrammarRule]
    nonterminals: list[str]
    terminals: list[str]
    nullable: list[str]


class GrammarPresetSummary(_Model):
    id: str
    name: str
    description: str


class GrammarPresetList(_Model):
    presets: list[GrammarPresetSummary]


class GrammarPresetDetail(GrammarPresetSummary):
    grammar: str
    examples: list[GrammarExample]


class ValidateGrammarRequest(_Model):
    grammar: str = Field(max_length=12_000)


class ValidateGrammarResponse(_Model):
    valid: bool
    diagnostics: list[GrammarDiagnostic]
    grammar: GrammarSummary | None


class ParseGrammarRequest(_Model):
    grammar: str = Field(max_length=12_000)
    sentence: str = Field(min_length=1, max_length=400)
    max_trees: int = Field(default=20, ge=1, le=50)


class ChartItemOut(_Model):
    rule: int
    dot: int
    origin: int
    end: int
    step: int = Field(description="Trace step at which the item was added.")


class ItemRefOut(_Model):
    set: int
    index: int


class TraceEventOut(_Model):
    step: int
    kind: Literal[
        "init", "predict", "nullable", "scan", "scan_fail", "complete", "accept", "reject"
    ]
    set: int
    item: ItemRefOut | None
    added: bool = Field(description="False if the item was already in the chart.")
    cause: ItemRefOut | None
    completed: ItemRefOut | None
    symbol: str | None
    token: int | None
    rule: int | None


class DerivationTree(_Model):
    symbol: str
    kind: Literal["nonterminal", "terminal"]
    start: int
    end: int
    rule: int | None
    token: int | None
    children: list[DerivationTree]


class ParseGrammarResponse(_Model):
    grammar: GrammarSummary
    diagnostics: list[GrammarDiagnostic]
    tokens: list[str]
    unknown_tokens: list[int] = Field(description="Positions of words that no rule produces.")
    accepted: bool
    tree_count: int = Field(description="Exact number of parse trees, capped at tree_count_cap.")
    tree_count_capped: bool
    trees: list[DerivationTree]
    chart: list[list[ChartItemOut]]
    trace: list[TraceEventOut]
    trace_truncated: bool
