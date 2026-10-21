"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from syntaxlab_api import __version__
from syntaxlab_api.api import health
from syntaxlab_api.api.v1 import grammar_routes, learning_routes, routes
from syntaxlab_api.errors import ApiError
from syntaxlab_api.glossary import load_glossaries
from syntaxlab_api.grammar.presets import load_presets
from syntaxlab_api.languages.config import load_languages_file
from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.learning.exercises import load_exercises
from syntaxlab_api.middleware import BodySizeLimitMiddleware, RateLimiter
from syntaxlab_api.security_headers import SecurityHeadersMiddleware
from syntaxlab_api.settings import Settings, get_settings

logger = logging.getLogger("syntaxlab_api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        languages_file = load_languages_file(settings.languages_file)
        registry = LanguageRegistry.from_config(languages_file, settings)
        app.state.registry = registry
        app.state.glossaries = load_glossaries(settings.glossary_dir, languages_file.schemes)
        app.state.grammar_presets = load_presets(settings.grammar_dir)
        app.state.exercises = load_exercises(settings.exercises_dir, app.state.grammar_presets)
        if settings.preload:
            for runtime in registry:
                runtime.start_loading()  # background, on each engine's own thread
        try:
            yield
        finally:
            registry.shutdown()

    app = FastAPI(
        title="SyntaxLab Parser API",
        version=__version__,
        description=(
            "Syntactic analysis from identified parsers, normalized to a language-independent "
            "schema. Languages and engines are configured, not hard-coded: see "
            "`GET /api/v1/languages` for what this deployment supports."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_burst)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        body: dict[str, object] = {"code": exc.code, "message": exc.message}
        if exc.details:
            body["details"] = exc.details
        return JSONResponse({"error": body}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Echo locations and messages, never the submitted values.
        problems = [
            {
                "loc": [str(p) for p in e.get("loc", ())],
                "msg": e.get("msg", ""),
                "type": e.get("type", ""),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "The request is malformed.",
                    "details": {"problems": problems},
                }
            },
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
            status_code=500,
        )

    app.include_router(health.router)
    app.include_router(routes.router)
    app.include_router(grammar_routes.router)
    app.include_router(learning_routes.router)
    return app
