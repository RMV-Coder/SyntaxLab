"""Test-only engine. Never registered in production configuration.

It produces *structurally valid but linguistically meaningless* output (whitespace tokens, a
right-branching chain) so that API plumbing, limits and error paths can be tested without
NLP models. Linguistic behaviour is tested separately against real models (tests/integration).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from typing import ClassVar

from syntaxlab_api.engines.base import Engine, EngineContext, EngineError
from syntaxlab_api.schemas.analysis import (
    Capability,
    ConstituencyAnalysis,
    ConstituencyNode,
    DependencyAnalysis,
    DependencyArc,
    SentenceAnalysis,
    StructureKind,
    Token,
)


class WhitespaceTestEngine(Engine):
    name: ClassVar[str] = "whitespace-test"

    #: Count of analyze() calls across instances, for cache assertions.
    calls = 0
    #: Set to hold analyses until released (for queue/overload tests).
    gate: ClassVar[threading.Event | None] = None

    def __init__(self, context: EngineContext) -> None:
        super().__init__(context)
        o = context.options
        self.structures = {StructureKind(s) for s in o.get("structures", ["dependency"])}
        self.fail_load = bool(o.get("fail_load", False))
        self.fail_analyze = bool(o.get("fail_analyze", False))
        self.invalid_output = bool(o.get("invalid_output", False))
        self.delay_s = float(o.get("delay_s", 0.0))
        self.loaded = False

    def capabilities(self) -> Mapping[Capability, str]:
        caps = {Capability.TOKENIZATION: "test/whitespace"}
        if StructureKind.DEPENDENCY in self.structures:
            caps[Capability.DEPENDENCY] = "test/chain"
        if StructureKind.CONSTITUENCY in self.structures:
            caps[Capability.CONSTITUENCY] = "test/flat"
        return caps

    @property
    def model_id(self) -> str:
        return "test:whitespace"

    def load(self) -> None:
        if self.fail_load:
            raise EngineError("simulated load failure")
        self.loaded = True

    def analyze(self, text: str, structures: frozenset[StructureKind]) -> list[SentenceAnalysis]:
        type(self).calls += 1
        if self.gate is not None:
            self.gate.wait(timeout=10)
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.fail_analyze:
            raise EngineError("simulated analysis failure")
        # Sentences end at " | " so tests can control sentence count explicitly.
        return [self._sentence(part.strip(), structures) for part in text.split(" | ")]

    def _sentence(self, text: str, structures: frozenset[StructureKind]) -> SentenceAnalysis:
        forms = text.split()
        n = len(forms)
        tokens = [Token(id=i + 1, form=f) for i, f in enumerate(forms)]
        dependency = None
        if StructureKind.DEPENDENCY in structures:
            arcs = [DependencyArc(dependent=i, head=i - 1, relation="dep") for i in range(2, n + 1)]
            arcs.insert(0, DependencyArc(dependent=1, head=0, relation="root"))
            if self.invalid_output:
                arcs[-1] = DependencyArc(dependent=n, head=n, relation="dep")  # self-loop
            dependency = DependencyAnalysis(
                scheme=self.scheme_for(Capability.DEPENDENCY), arcs=arcs
            )
        constituency = None
        if StructureKind.CONSTITUENCY in structures:
            pre = [
                ConstituencyNode(id=f"t{i}", label="X", token_id=i, span=(i, i))
                for i in range(1, n + 1)
            ]
            root = ConstituencyNode(id="r", label="S", children=[p.id for p in pre], span=(1, n))
            constituency = ConstituencyAnalysis(
                scheme=self.scheme_for(Capability.CONSTITUENCY), root="r", nodes=[root, *pre]
            )
        return SentenceAnalysis(
            text=text, tokens=tokens, dependency=dependency, constituency=constituency
        )
