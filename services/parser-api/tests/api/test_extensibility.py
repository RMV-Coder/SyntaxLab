"""Adding a language is a configuration change, not a code change.

These tests add languages purely through YAML, the way an operator would, and check that the
API exposes them with exactly the capabilities their engine provides.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from syntaxlab_api.main import create_app
from syntaxlab_api.settings import SERVICE_ROOT, Settings


def client_for(tmp_path: Path, extra_languages: list[dict[str, object]]) -> TestClient:
    shipped = yaml.safe_load((SERVICE_ROOT / "config" / "languages.yaml").read_text("utf-8"))
    shipped["languages"].extend(extra_languages)
    path = tmp_path / "languages.yaml"
    path.write_text(yaml.safe_dump(shipped, allow_unicode=True), encoding="utf-8")
    # preload=False: describing languages never needs their models.
    return TestClient(create_app(Settings(languages_file=path, preload=False)))


def test_new_stanza_language_from_yaml_only(tmp_path: Path) -> None:
    spanish = {
        "code": "es",
        "name": "Spanish",
        "native_name": "Español",
        "engine": "stanza",
        "engine_options": {
            "lang": "es",
            "processors": ["tokenize", "mwt", "pos", "lemma", "depparse"],
        },
        "schemes": {"pos": "ud-upos", "morphology": "ud-feats", "dependency": "ud-2"},
        "samples": [{"text": "El niño come arroz."}],
    }
    with client_for(tmp_path, [spanish]) as client:
        codes = [lang["code"] for lang in client.get("/api/v1/languages").json()["languages"]]
        assert codes == ["en", "es"]
        detail = client.get("/api/v1/languages/es").json()
        assert detail["native_name"] == "Español"
        assert detail["structures"] == ["dependency"]  # no constituency processor configured
        assert {c["capability"] for c in detail["capabilities"]} == {
            "tokenization",
            "pos",
            "morphology",
            "lemma",
            "dependency",
        }
        # The shared UD glossaries apply to the new language automatically.
        assert client.get("/api/v1/schemes/ud-2").status_code == 200
        # Asking for a structure the language lacks is refused, never substituted.
        response = client.post(
            "/api/v1/parse",
            json={"language": "es", "text": "El niño come arroz.", "structures": ["constituency"]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unsupported_structure"


def test_new_engine_plugs_in_by_reference(tmp_path: Path) -> None:
    # Any importable Engine subclass can serve a language; here the test engine stands in for
    # a third-party package that would normally register itself as an entry point.
    toy = {
        "code": "tl",
        "name": "Filipino (Tagalog)",
        "aliases": ["fil"],
        "engine": "tests.support.engines:WhitespaceTestEngine",
        "engine_options": {"structures": ["dependency"]},
        "schemes": {"dependency": "ud-2"},
    }
    with client_for(tmp_path, [toy]) as client:
        assert client.get("/api/v1/languages/fil").json()["code"] == "tl"
        body = client.post("/api/v1/parse", json={"language": "fil", "text": "a b c"}).json()
        assert body["language"]["code"] == "tl"
        assert body["provenance"]["engine"] == "whitespace-test"
