"""Normalized, language-independent analysis schema.

Design rules (see docs/architecture.md §6):
- Token ids are 1-based *syntactic words*, as in CoNLL-U. Orthographic tokens that an engine
  splits into several words (English "don't" -> "do" + "n't") are kept in `multiword_tokens`
  so the surface text can always be reconstructed.
- Engine-specific information is preserved (`xpos`, raw feature values) rather than discarded.
- There is deliberately no confidence field: none of the supported engines exposes calibrated
  scores, and SyntaxLab does not invent them.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Capability(StrEnum):
    """What an engine can produce for a language."""

    TOKENIZATION = "tokenization"
    POS = "pos"
    LEMMA = "lemma"
    MORPHOLOGY = "morphology"
    DEPENDENCY = "dependency"
    CONSTITUENCY = "constituency"


class StructureKind(StrEnum):
    """Structural analyses a client can request. Token-level annotations come with every parse."""

    DEPENDENCY = "dependency"
    CONSTITUENCY = "constituency"


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )


class Token(_Model):
    id: int = Field(ge=1, description="1-based syntactic word index within the sentence.")
    form: str
    lemma: str | None = None
    upos: str | None = Field(default=None, description="Universal POS tag, when available.")
    xpos: str | None = Field(default=None, description="Language/treebank-specific POS tag.")
    feats: dict[str, str] = Field(default_factory=dict, description="Morphological features.")
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)


class MultiwordToken(_Model):
    first: int = Field(ge=1, description="First word id covered by this orthographic token.")
    last: int = Field(ge=1, description="Last word id covered (inclusive).")
    form: str
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)


class DependencyArc(_Model):
    dependent: int = Field(ge=1)
    head: int = Field(ge=0, description="0 denotes the artificial root.")
    relation: str


class DependencyAnalysis(_Model):
    scheme: str = Field(description="Annotation scheme id, e.g. 'ud-2'.")
    arcs: list[DependencyArc]


class ConstituencyNode(_Model):
    id: str
    label: str
    children: list[str] = Field(
        default_factory=list, description="Child node ids, in surface order."
    )
    token_id: int | None = Field(
        default=None,
        description="Set on pre-terminal nodes: the word this node dominates. Such nodes have no "
        "children.",
    )
    span: tuple[int, int] = Field(description="Inclusive word-id span [first, last].")


class ConstituencyAnalysis(_Model):
    scheme: str = Field(description="Annotation scheme id, e.g. 'ptb-revised'.")
    root: str
    nodes: list[ConstituencyNode]


class SentenceAnalysis(_Model):
    text: str
    start_char: int | None = None
    end_char: int | None = None
    tokens: list[Token]
    multiword_tokens: list[MultiwordToken] = Field(default_factory=list)
    dependency: DependencyAnalysis | None = None
    constituency: ConstituencyAnalysis | None = None


class Notice(_Model):
    """A warning or limitation the user should see alongside an analysis."""

    code: str
    message: str


class ComponentInfo(_Model):
    capability: Capability
    scheme: str | None = None
    component: str = Field(description="Engine component that produced this layer.")


class Provenance(_Model):
    engine: str
    engine_version: str | None = None
    model: str | None = None
    components: list[ComponentInfo]
    processing_ms: float = Field(ge=0)
    cached: bool = False
