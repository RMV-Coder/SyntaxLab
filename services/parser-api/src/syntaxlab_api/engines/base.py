"""The engine plug-in contract.

An *engine* wraps one NLP back-end (Stanza, spaCy, a custom parser, ...) and turns its output
into SyntaxLab's normalized schema. Engines are generic: the same engine class serves every
language its back-end supports, configured per language in ``config/languages.yaml``.

Adding a language never requires changing this package:
- if an existing engine supports it, add a YAML entry;
- otherwise, ship an engine in any installed Python package and register it under the
  ``syntaxlab.engines`` entry-point group (or reference it as ``"module.path:ClassName"``).

Contract every engine must honour (enforced by ``syntaxlab_api.analysis.validate`` and the
engine conformance tests):
- report exactly the capabilities it really produces; never emulate one from another
  (e.g. no constituency trees derived from dependencies);
- return the back-end's analysis faithfully: no relabelling, no re-attachment, no fabricated
  alternatives or confidence scores;
- raise ``EngineError`` for back-end failures instead of returning partial data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from syntaxlab_api.schemas.analysis import Capability, SentenceAnalysis, StructureKind


class EngineError(Exception):
    """A back-end failure (model missing, load error, crash during analysis)."""


class EngineConfigError(EngineError):
    """The engine options in the language configuration are invalid."""


@dataclass(frozen=True)
class EngineContext:
    """Everything an engine instance needs, resolved from configuration and settings."""

    language: str
    options: Mapping[str, Any]
    schemes: Mapping[Capability, str] = field(default_factory=dict)
    cpu_threads: int = 1
    models_dir: Path | None = None


class Engine(ABC):
    #: Registry name, e.g. "stanza". Must match the entry-point name.
    name: ClassVar[str]

    def __init__(self, context: EngineContext) -> None:
        self.context = context

    # ------------------------------------------------------------------ metadata

    @abstractmethod
    def capabilities(self) -> Mapping[Capability, str]:
        """Capabilities this configured instance provides, mapped to the producing component.

        Must be computable *without* loading models, so the API can describe languages
        before they are ready.
        """

    @property
    def engine_version(self) -> str | None:
        return None

    @property
    def model_id(self) -> str | None:
        return None

    # ------------------------------------------------------------------ lifecycle

    def download(self) -> None:  # noqa: B027 - optional hook, default is a no-op
        """Fetch model resources. Called by the CLI at build time, never during requests."""

    @abstractmethod
    def load(self) -> None:
        """Load models into memory. Called once, on the engine's dedicated worker thread."""

    def close(self) -> None:  # noqa: B027 - optional hook, default is a no-op
        """Release resources."""

    # ------------------------------------------------------------------ analysis

    @abstractmethod
    def analyze(self, text: str, structures: frozenset[StructureKind]) -> list[SentenceAnalysis]:
        """Analyze already-validated, NFC-normalized text.

        ``structures`` is guaranteed to be a subset of the structures this instance supports.
        Token-level layers (POS, lemma, features) are always returned when supported.
        """

    # ------------------------------------------------------------------ helpers

    def scheme_for(self, capability: Capability) -> str:
        try:
            return self.context.schemes[capability]
        except KeyError as exc:  # pragma: no cover - guarded by config validation
            raise EngineConfigError(
                f"no annotation scheme configured for {capability.value!r}"
            ) from exc
