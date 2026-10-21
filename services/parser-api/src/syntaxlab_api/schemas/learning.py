"""Request/response models for learning exercises."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from syntaxlab_api.schemas.grammar import DerivationTree


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


ExerciseKind = Literal["pos", "dependency", "constituency"]


class ExerciseSummary(_Model):
    id: str
    kind: ExerciseKind
    title: str
    difficulty: int
    language: str | None


class ExerciseList(_Model):
    exercises: list[ExerciseSummary]


class ExerciseToken(_Model):
    id: int = Field(description="1-based word position.")
    form: str


class LabelOption(_Model):
    value: str
    name: str | None = Field(description="Plain-language name from the curated glossary, if any.")


class AnswerKeySource(_Model):
    kind: Literal["gold_annotation", "grammar_parses"]
    description: str
    treebank: str | None
    release: str | None
    sent_id: str | None
    license: str | None


class ExerciseDetail(ExerciseSummary):
    """An exercise *without* its answer key."""

    instructions: str
    tokens: list[ExerciseToken]
    options: list[LabelOption] = Field(
        description="POS tags (pos), relations (dependency) or categories (constituency)."
    )
    grammar: str | None = Field(description="Grammar text, for constituency exercises.")
    grammar_name: str | None
    answer_key: AnswerKeySource


# ---------------------------------------------------------------------- answers


class PosAnswer(_Model):
    kind: Literal["pos"]
    tags: list[str | None] = Field(description="One tag per word (null = not answered).")


class DependencyAnswerArc(_Model):
    dependent: int = Field(ge=1)
    head: int | None = Field(ge=0, description="0 = root; null = not answered.")
    relation: str | None


class DependencyAnswer(_Model):
    kind: Literal["dependency"]
    arcs: list[DependencyAnswerArc]


class ConstituentIn(_Model):
    label: str = Field(min_length=1, max_length=32)
    start: int = Field(ge=0, description="First word (0-based).")
    end: int = Field(ge=1, description="One past the last word.")


class ConstituencyAnswer(_Model):
    kind: Literal["constituency"]
    constituents: list[ConstituentIn] = Field(
        max_length=200,
        description="In creation order; for identical spans, earlier entries dominate later ones.",
    )


Answer = Annotated[PosAnswer | DependencyAnswer | ConstituencyAnswer, Field(discriminator="kind")]


class CheckRequest(_Model):
    answer: Answer


# ---------------------------------------------------------------------- feedback

TokenStatus = Literal["correct", "incorrect", "partial", "unanswered"]


class PosItem(_Model):
    token: int
    given: str | None
    expected: str
    status: TokenStatus


class PosFeedback(_Model):
    kind: Literal["pos"]
    correct: int
    total: int
    items: list[PosItem]


class DependencyItem(_Model):
    token: int
    given_head: int | None
    given_relation: str | None
    expected_head: int
    expected_relation: str
    head_correct: bool
    relation_status: TokenStatus = Field(
        description="partial = right base relation, but the annotation uses a subtype "
        "(or vice versa)."
    )


class DependencyFeedback(_Model):
    kind: Literal["dependency"]
    heads_correct: int
    relations_correct: int
    total: int
    items: list[DependencyItem]


ConstituentStatus = Literal["correct", "missing", "other_reading", "unlicensed"]


class ConstituentFeedback(_Model):
    label: str
    start: int
    end: int
    status: ConstituentStatus


class StructureProblem(_Model):
    code: Literal[
        "out_of_range",
        "crossing",
        "no_root",
        "several_roots",
        "uncovered_word",
        "unknown_category",
        "no_rule",
    ]
    constituent: int | None = Field(description="Index in the submitted list, if specific.")
    label: str | None
    rule: str | None = Field(description="For no_rule: the rule the tree would need.")
    words: str | None


class ConstituencyFeedback(_Model):
    kind: Literal["constituency"]
    status: Literal["matches", "partial", "invalid"]
    parse_count: int = Field(description="Number of parses the grammar allows for the sentence.")
    parses_compared: int
    matched_parse: int | None = Field(description="1-based index of the parse matched exactly.")
    closest_parse: int | None
    precision: float
    recall: float
    constituents: list[ConstituentFeedback]
    problems: list[StructureProblem]
    reference: DerivationTree | None = Field(
        description="The matched or closest parse, with empty constituents removed."
    )


Feedback = Annotated[
    PosFeedback | DependencyFeedback | ConstituencyFeedback, Field(discriminator="kind")
]


class CheckResponse(_Model):
    exercise: str
    feedback: Feedback
