# SyntaxLab Parser API

FastAPI service that runs configured syntactic-analysis engines and returns a normalized,
language-independent analysis. See [`docs/architecture.md`](../../docs/architecture.md) and
[`docs/api.md`](../../docs/api.md).

```bash
uv sync --extra stanza                 # Python 3.12 is installed automatically by uv
uv run syntaxlab-api download-models   # ~430 MB for English
uv run uvicorn syntaxlab_api.main:create_app --factory --reload
uv run pytest                          # unit + API tests (no models needed)
uv run pytest -m models                # integration tests against real models
```

Languages are declared in [`config/languages.yaml`](config/languages.yaml); engines are
plug-ins (see `src/syntaxlab_api/engines/base.py`).
