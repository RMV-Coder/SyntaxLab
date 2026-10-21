"""Algorithm Lab endpoints: preset grammars, grammar validation, and Earley parsing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from syntaxlab_api import errors
from syntaxlab_api.api.v1.routes import ERROR_RESPONSES, rate_limited
from syntaxlab_api.grammar import service
from syntaxlab_api.grammar.presets import GrammarPreset
from syntaxlab_api.schemas.grammar import (
    GrammarPresetDetail,
    GrammarPresetList,
    GrammarPresetSummary,
    ParseGrammarRequest,
    ParseGrammarResponse,
    ValidateGrammarRequest,
    ValidateGrammarResponse,
)

router = APIRouter(prefix="/api/v1/grammar", tags=["algorithm-lab"])


def _presets(request: Request) -> dict[str, GrammarPreset]:
    presets: dict[str, GrammarPreset] = request.app.state.grammar_presets
    return presets


@router.get("/presets", response_model=GrammarPresetList, summary="Preset educational grammars")
def list_presets(request: Request) -> GrammarPresetList:
    return GrammarPresetList(
        presets=[
            GrammarPresetSummary(id=p.id, name=p.name, description=p.description)
            for p in _presets(request).values()
        ]
    )


@router.get(
    "/presets/{preset_id}",
    response_model=GrammarPresetDetail,
    responses={404: ERROR_RESPONSES[404]},
    summary="A preset grammar with example sentences and their expected outcomes",
)
def get_preset(preset_id: str, request: Request) -> GrammarPresetDetail:
    preset = _presets(request).get(preset_id)
    if preset is None:
        raise errors.UnknownGrammar(
            f"No preset grammar {preset_id!r}.", details={"available": sorted(_presets(request))}
        )
    return GrammarPresetDetail(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        grammar=preset.grammar,
        examples=preset.examples,
    )


@router.post(
    "/validate",
    response_model=ValidateGrammarResponse,
    responses={422: ERROR_RESPONSES[422]},
    summary="Check a grammar and report problems with line numbers",
)
def validate_grammar(body: ValidateGrammarRequest) -> ValidateGrammarResponse:
    return service.validate(body.grammar)


@router.post(
    "/parse",
    response_model=ParseGrammarResponse,
    responses=ERROR_RESPONSES,
    dependencies=[Depends(rate_limited)],
    summary="Run the Earley parser and return its full execution trace and parse trees",
)
def parse_with_grammar(body: ParseGrammarRequest) -> ParseGrammarResponse:
    # Pure-Python and bounded (≤ 200 rules, ≤ 20 words); FastAPI runs sync handlers in a
    # thread pool, so this does not block the event loop.
    return service.parse(body.grammar, body.sentence, body.max_trees)
