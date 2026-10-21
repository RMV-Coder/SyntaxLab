"""Per-language runtime: model lifecycle, serialized inference, back-pressure and caching.

Each language owns one single-threaded executor. The engine is loaded *and* run on that
thread, which (a) serializes inference, because NLP pipelines are not documented as
thread-safe, and (b) guarantees the load finishes before the first analysis (FIFO queue).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from syntaxlab_api import errors
from syntaxlab_api.analysis.validate import StructureError, validate_sentence
from syntaxlab_api.engines.base import Engine, EngineError
from syntaxlab_api.languages.config import LanguageConfig, SchemeConfig
from syntaxlab_api.schemas.analysis import (
    Capability,
    ComponentInfo,
    Provenance,
    SentenceAnalysis,
    StructureKind,
)
from syntaxlab_api.schemas.api import LanguageStatus

logger = logging.getLogger(__name__)

STRUCTURE_CAPABILITY: Mapping[StructureKind, Capability] = {
    StructureKind.DEPENDENCY: Capability.DEPENDENCY,
    StructureKind.CONSTITUENCY: Capability.CONSTITUENCY,
}


@dataclass(frozen=True)
class Limits:
    max_chars: int
    max_words: int
    max_sentences: int


@dataclass(frozen=True)
class AnalysisOutcome:
    sentences: list[SentenceAnalysis]
    provenance: Provenance


class LanguageRuntime:
    def __init__(
        self,
        config: LanguageConfig,
        engine: Engine,
        schemes: Mapping[str, SchemeConfig],
        *,
        limits: Limits,
        max_queue: int,
        timeout_s: float,
        cache_size: int,
    ) -> None:
        self.config = config
        self.engine = engine
        self.schemes = schemes
        self.limits = limits
        self.capabilities: Mapping[Capability, str] = dict(engine.capabilities())
        self.structures: frozenset[StructureKind] = frozenset(
            s for s, c in STRUCTURE_CAPABILITY.items() if c in self.capabilities
        )
        self._max_queue = max_queue
        self._timeout_s = timeout_s
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"engine-{config.code}"
        )
        self._lock = threading.Lock()
        self._status = LanguageStatus.NOT_LOADED
        self._load_future: Future[None] | None = None
        self._pending = 0
        self._cache: OrderedDict[tuple[str, frozenset[StructureKind]], AnalysisOutcome] = (
            OrderedDict()
        )
        self._cache_size = cache_size

    # ------------------------------------------------------------------ lifecycle

    @property
    def code(self) -> str:
        return self.config.code

    @property
    def status(self) -> LanguageStatus:
        return self._status

    def start_loading(self) -> Future[None]:
        with self._lock:
            if self._load_future is None:
                self._status = LanguageStatus.LOADING
                self._load_future = self._executor.submit(self._load)
            return self._load_future

    def _load(self) -> None:
        started = time.perf_counter()
        try:
            self.engine.load()
        except Exception:
            logger.exception("engine load failed for language %s", self.code)
            self._status = LanguageStatus.FAILED
            return
        self._status = LanguageStatus.READY
        logger.info("language %s ready in %.1fs", self.code, time.perf_counter() - started)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.engine.close()
        except Exception:  # pragma: no cover - best effort on shutdown
            logger.exception("engine close failed for %s", self.code)

    # ------------------------------------------------------------------ analysis

    async def analyze(self, text: str, structures: frozenset[StructureKind]) -> AnalysisOutcome:
        unsupported = structures - self.structures
        if unsupported:
            raise errors.UnsupportedStructure(
                f"{self.config.name} does not support "
                + ", ".join(sorted(s.value for s in unsupported))
                + " analysis.",
                details={"supported": sorted(s.value for s in self.structures)},
            )
        if self._status is LanguageStatus.FAILED:
            raise errors.ModelUnavailable(f"The {self.config.name} models failed to load.")
        self.start_loading()

        key = (text, structures)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return AnalysisOutcome(
                sentences=cached.sentences,
                provenance=cached.provenance.model_copy(update={"cached": True}),
            )

        with self._lock:
            if self._pending >= self._max_queue:
                raise errors.Overloaded(
                    "The analyzer is busy. Please retry shortly.", headers={"Retry-After": "5"}
                )
            self._pending += 1
        future = self._executor.submit(self._run, text, structures)
        future.add_done_callback(self._release)
        try:
            outcome = await asyncio.wait_for(asyncio.wrap_future(future), self._timeout_s)
        except TimeoutError as exc:
            raise errors.AnalysisTimeout(
                f"Analysis took longer than {self._timeout_s:.0f}s. Try a shorter sentence."
            ) from exc

        if self._cache_size:
            self._cache[key] = outcome
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return outcome

    def _release(self, _: Future[AnalysisOutcome]) -> None:
        with self._lock:
            self._pending -= 1

    def _run(self, text: str, structures: frozenset[StructureKind]) -> AnalysisOutcome:
        # Runs on the engine thread, after any pending load (single-worker FIFO executor).
        if self._status is not LanguageStatus.READY:
            raise errors.ModelUnavailable(f"The {self.config.name} models are not available.")
        started = time.perf_counter()
        try:
            sentences = self.engine.analyze(text, structures)
        except EngineError as exc:
            logger.exception("engine failure for language %s", self.code)
            raise errors.EngineFailure("The analyzer failed on this input.") from exc
        try:
            for sentence in sentences:
                validate_sentence(sentence)
        except StructureError as exc:
            logger.error("invalid engine output for %s: %s", self.code, exc)
            raise errors.InvalidEngineOutput(
                "The parser produced a structurally invalid analysis; it was not shown."
            ) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        return AnalysisOutcome(
            sentences=sentences, provenance=self._provenance(structures, elapsed_ms)
        )

    def _provenance(self, structures: frozenset[StructureKind], elapsed_ms: float) -> Provenance:
        produced = {
            Capability.TOKENIZATION,
            Capability.POS,
            Capability.LEMMA,
            Capability.MORPHOLOGY,
        }
        produced |= {STRUCTURE_CAPABILITY[s] for s in structures}
        components = [
            ComponentInfo(
                capability=cap,
                scheme=self.config.schemes.get(cap),
                component=component,
            )
            for cap, component in self.engine.capabilities().items()
            if cap in produced
        ]
        return Provenance(
            engine=self.engine.name,
            engine_version=self.engine.engine_version,
            model=self.engine.model_id,
            components=components,
            processing_ms=round(elapsed_ms, 1),
        )
