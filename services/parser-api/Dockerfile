# SyntaxLab parser API: production image.
#
# - Python 3.12 and CPU-only torch (see docs/research/nlp-model-evaluation.md).
# - Models are downloaded at *build* time and baked into the image; the service never downloads
#   anything at runtime (Stanza runs with download_method=None).
# - Runs as a non-root user on port 7860 (the Hugging Face Spaces default; override with PORT).
#
#   docker build -t syntaxlab-api services/parser-api
#   docker run --rm -p 7860:7860 --cpus 2 --memory 4g syntaxlab-api

# ---------------------------------------------------------------- build stage
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# Dependencies first (cached unless the lockfile changes).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra stanza --no-install-project
# Then the application itself.
COPY src ./src
COPY config ./config
COPY data ./data
RUN uv sync --locked --no-dev --extra stanza

# Bake the models for every configured language into the image.
ENV SYNTAXLAB_MODELS_DIR=/app/.models
RUN /app/.venv/bin/syntaxlab-api download-models \
 && /app/.venv/bin/syntaxlab-api check

# ---------------------------------------------------------------- runtime stage
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 syntaxlab
WORKDIR /app
COPY --from=build --chown=syntaxlab:syntaxlab /app /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    SYNTAXLAB_MODELS_DIR=/app/.models \
    SYNTAXLAB_PRELOAD=true \
    PORT=7860

# Proxies whose X-Forwarded-For uvicorn believes when it resolves the client address (used for
# per-client rate limits). Never "*": uvicorn would then take the leftmost address, which the
# client controls. Private ranges cover a platform's internal proxies; override for other setups.
ENV FORWARDED_ALLOW_IPS="127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

USER syntaxlab
EXPOSE 7860

# Liveness only: /ready reports model readiness (models take tens of seconds to load).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# One worker: every extra worker would hold its own copy of the models.
CMD ["sh", "-c", "exec uvicorn syntaxlab_api.main:create_app --factory --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers"]
