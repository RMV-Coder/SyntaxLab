from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from syntaxlab_api.main import create_app
from syntaxlab_api.settings import Settings
from tests.support.engines import WhitespaceTestEngine

TEST_ENGINE = "tests.support.engines:WhitespaceTestEngine"

SCHEMES = {
    "test-dep": {"name": "Test dependency scheme"},
    "test-con": {"name": "Test constituency scheme"},
}


def language(code: str, **overrides: Any) -> dict[str, Any]:
    options = overrides.pop("engine_options", {"structures": ["dependency", "constituency"]})
    schemes = {}
    if "dependency" in options.get("structures", ["dependency"]):
        schemes["dependency"] = "test-dep"
    if "constituency" in options.get("structures", []):
        schemes["constituency"] = "test-con"
    entry: dict[str, Any] = {
        "code": code,
        "name": f"Test {code}",
        "engine": TEST_ENGINE,
        "engine_options": options,
        "schemes": schemes,
        "samples": [{"text": "a b c", "note": "sample"}],
        "notes": ["test language"],
    }
    entry.update(overrides)
    return entry


def write_config(tmp_path: Path, languages: list[dict[str, Any]]) -> Path:
    path = tmp_path / "languages.yaml"
    path.write_text(yaml.safe_dump({"schemes": SCHEMES, "languages": languages}), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _reset_test_engine() -> Iterator[None]:
    WhitespaceTestEngine.calls = 0
    WhitespaceTestEngine.gate = None
    yield
    if WhitespaceTestEngine.gate is not None:
        WhitespaceTestEngine.gate.set()
    WhitespaceTestEngine.gate = None


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def factory(languages: list[dict[str, Any]] | None = None, **settings: Any) -> TestClient:
        path = write_config(tmp_path, languages or [language("xx", aliases=["xxx"])])
        defaults: dict[str, Any] = {
            "languages_file": path,
            "models_dir": tmp_path / "models",
            "preload": True,
            "cpu_threads": 1,
            "rate_limit_per_minute": 0,
        }
        defaults.update(settings)
        client = TestClient(create_app(Settings(**defaults)))
        client.__enter__()  # run lifespan
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


def wait_ready(client: TestClient, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        response = client.get("/ready")
        body: dict[str, Any] = response.json()
        if body["ready"] or time.monotonic() > deadline:
            return body
        time.sleep(0.01)
