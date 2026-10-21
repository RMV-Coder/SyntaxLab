"""Version 1 public API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from syntaxlab_api import errors
from syntaxlab_api.analysis.text_input import check_analysis_size, normalize_text
from syntaxlab_api.glossary import Glossary
from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.languages.runtime import LanguageRuntime
from syntaxlab_api.middleware import RateLimiter
from syntaxlab_api.schemas.analysis import Capability
from syntaxlab_api.schemas.api import (
    CapabilityInfo,
    ErrorResponse,
    LanguageDetail,
    LanguageLimits,
    LanguageList,
    LanguageRef,
    LanguageSummary,
    ParseRequest,
    ParseResponse,
    SampleSentence,
    SchemeInfo,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Unsupported language"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {"model": ErrorResponse, "description": "Invalid input or unsupported structure"},
    429: {"model": ErrorResponse, "description": "Rate limited"},
    500: {"model": ErrorResponse, "description": "Engine failure or invalid engine output"},
    503: {"model": ErrorResponse, "description": "Models unavailable or analyzer overloaded"},
    504: {"model": ErrorResponse, "description": "Analysis timed out"},
}

# Order in which capabilities are listed to clients.
_CAPABILITY_ORDER = list(Capability)


def get_registry(request: Request) -> LanguageRegistry:
    registry: LanguageRegistry = request.app.state.registry
    return registry


def rate_limited(request: Request) -> None:
    limiter: RateLimiter = request.app.state.rate_limiter
    limiter.check(request)


Registry = Annotated[LanguageRegistry, Depends(get_registry)]


def _capabilities(runtime: LanguageRuntime) -> list[CapabilityInfo]:
    infos = []
    for cap in sorted(runtime.capabilities, key=_CAPABILITY_ORDER.index):
        scheme_id = runtime.config.schemes.get(cap)
        scheme = None
        if scheme_id is not None:
            cfg = runtime.schemes[scheme_id]
            scheme = SchemeInfo(id=scheme_id, name=cfg.name, url=cfg.url)
        infos.append(
            CapabilityInfo(capability=cap, scheme=scheme, component=runtime.capabilities[cap])
        )
    return infos


def _summary(runtime: LanguageRuntime) -> LanguageSummary:
    cfg = runtime.config
    return LanguageSummary(
        code=cfg.code,
        name=cfg.name,
        native_name=cfg.native_name,
        aliases=cfg.aliases,
        status=runtime.status,
        capabilities=_capabilities(runtime),
        structures=sorted(runtime.structures),
    )


@router.get("/languages", response_model=LanguageList, summary="List supported languages")
def list_languages(registry: Registry) -> LanguageList:
    return LanguageList(languages=[_summary(r) for r in registry])


@router.get(
    "/languages/{code}",
    response_model=LanguageDetail,
    responses={404: _ERRORS[404]},
    summary="Describe one language: capabilities, schemes, limits, samples",
)
def get_language(code: str, registry: Registry) -> LanguageDetail:
    runtime = registry.get(code)
    cfg = runtime.config
    return LanguageDetail(
        **_summary(runtime).model_dump(),
        engine=cfg.engine,
        samples=[SampleSentence(text=s.text, note=s.note) for s in cfg.samples],
        notes=cfg.notes,
        limits=LanguageLimits(
            max_chars=runtime.limits.max_chars,
            max_words=runtime.limits.max_words,
            max_sentences=runtime.limits.max_sentences,
        ),
    )


@router.post(
    "/parse",
    response_model=ParseResponse,
    responses=_ERRORS,
    dependencies=[Depends(rate_limited)],
    summary="Analyze a sentence",
)
async def parse(body: ParseRequest, registry: Registry) -> ParseResponse:
    runtime = registry.get(body.language)
    text = normalize_text(body.text, runtime.limits)
    structures = frozenset(body.structures) if body.structures is not None else runtime.structures
    outcome = await runtime.analyze(text, structures)
    check_analysis_size(
        sentence_count=len(outcome.sentences),
        word_count=sum(len(s.tokens) for s in outcome.sentences),
        limits=runtime.limits,
    )
    return ParseResponse(
        language=LanguageRef(code=runtime.code, name=runtime.config.name),
        text=text,
        sentences=outcome.sentences,
        provenance=outcome.provenance,
    )


@router.get(
    "/schemes/{scheme_id}",
    response_model=Glossary,
    responses={404: _ERRORS[404]},
    summary="Curated explanations of the labels of an annotation scheme",
)
def get_scheme_glossary(scheme_id: str, request: Request) -> Glossary:
    glossaries: dict[str, Glossary] = request.app.state.glossaries
    glossary = glossaries.get(scheme_id)
    if glossary is None:
        raise errors.UnknownScheme(
            f"No curated glossary is available for scheme {scheme_id!r}.",
            details={"available": sorted(glossaries)},
        )
    return glossary
