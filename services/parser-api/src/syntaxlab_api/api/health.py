"""Liveness and readiness probes (unversioned, for infrastructure)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.schemas.api import HealthResponse, LanguageStatus, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness: the process serves HTTP")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Not ready"}},
    summary="Readiness: configured models are usable",
)
def ready(request: Request) -> JSONResponse:
    registry: LanguageRegistry = request.app.state.registry
    statuses = {r.code: r.status for r in registry}
    if request.app.state.settings.preload:
        is_ready = all(s is LanguageStatus.READY for s in statuses.values())
    else:  # lazy loading: ready unless something is known to be broken
        is_ready = all(s is not LanguageStatus.FAILED for s in statuses.values())
    body = ReadinessResponse(ready=is_ready, languages=statuses)
    return JSONResponse(body.model_dump(mode="json"), status_code=200 if is_ready else 503)
