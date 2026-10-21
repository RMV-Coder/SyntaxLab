"""Builds language runtimes from configuration and resolves language codes/aliases."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from syntaxlab_api import errors
from syntaxlab_api.engines.base import EngineContext
from syntaxlab_api.engines.registry import resolve_engine
from syntaxlab_api.languages.config import ConfigError, LanguagesFile
from syntaxlab_api.languages.runtime import STRUCTURE_CAPABILITY, LanguageRuntime, Limits
from syntaxlab_api.settings import Settings

logger = logging.getLogger(__name__)


class LanguageRegistry:
    def __init__(self, runtimes: list[LanguageRuntime], languages_file: LanguagesFile) -> None:
        self._runtimes = {r.code: r for r in runtimes}
        self._index: dict[str, str] = {}
        for runtime in runtimes:
            for key in (runtime.code.lower(), *runtime.config.aliases):
                self._index[key] = runtime.code
        self.file = languages_file

    @classmethod
    def from_config(cls, languages_file: LanguagesFile, settings: Settings) -> LanguageRegistry:
        wanted = (
            {c.lower() for c in settings.enabled_languages} if settings.enabled_languages else None
        )
        runtimes: list[LanguageRuntime] = []
        for lang in languages_file.languages:
            if not lang.enabled or (wanted is not None and lang.code.lower() not in wanted):
                continue
            engine_cls = resolve_engine(lang.engine)
            engine = engine_cls(
                EngineContext(
                    language=lang.code,
                    options=lang.engine_options,
                    schemes=lang.schemes,
                    cpu_threads=settings.cpu_threads,
                    models_dir=settings.models_dir,
                )
            )
            provided = set(engine.capabilities())
            # Every structure the engine produces must say which annotation scheme it follows,
            # and the config must not claim schemes for layers the engine cannot produce.
            for capability in STRUCTURE_CAPABILITY.values():
                if capability in provided and capability not in lang.schemes:
                    raise ConfigError(
                        f"language {lang.code!r}: engine provides {capability.value} but no "
                        f"scheme is configured for it"
                    )
            claimed_only = set(lang.schemes) - provided
            if claimed_only:
                raise ConfigError(
                    f"language {lang.code!r}: schemes configured for capabilities the engine "
                    f"does not provide: {sorted(c.value for c in claimed_only)}"
                )
            limits = Limits(
                max_chars=lang.limits.max_chars or settings.default_max_chars,
                max_words=lang.limits.max_words or settings.default_max_words,
                max_sentences=lang.limits.max_sentences or settings.default_max_sentences,
            )
            runtimes.append(
                LanguageRuntime(
                    lang,
                    engine,
                    languages_file.schemes,
                    limits=limits,
                    max_queue=settings.max_queue,
                    timeout_s=settings.analysis_timeout_s,
                    cache_size=settings.cache_size,
                )
            )
            logger.info("registered language %s (engine=%s)", lang.code, lang.engine)
        if wanted is not None:
            missing = wanted - {r.code.lower() for r in runtimes}
            if missing:
                raise ConfigError(
                    f"enabled_languages lists unknown/disabled codes: {sorted(missing)}"
                )
        return cls(runtimes, languages_file)

    def __iter__(self) -> Iterator[LanguageRuntime]:
        return iter(self._runtimes.values())

    def __len__(self) -> int:
        return len(self._runtimes)

    def get(self, code_or_alias: str) -> LanguageRuntime:
        code = self._index.get(code_or_alias.strip().lower())
        if code is None:
            raise errors.UnsupportedLanguage(
                f"Language {code_or_alias!r} is not supported.",
                details={"supported": sorted(self._runtimes)},
            )
        return self._runtimes[code]

    def shutdown(self) -> None:
        for runtime in self._runtimes.values():
            runtime.shutdown()
