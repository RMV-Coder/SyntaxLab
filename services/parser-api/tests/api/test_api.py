"""HTTP-level tests with the test engine (no NLP models)."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ClientFactory, language, wait_ready
from tests.support.engines import WhitespaceTestEngine


def parse(client: TestClient, text: str, lang: str = "xx", **extra: object) -> object:
    return client.post("/api/v1/parse", json={"language": lang, "text": text, **extra})


class TestHealth:
    def test_health_is_immediate(self, make_client: ClientFactory) -> None:
        assert make_client().get("/health").json() == {"status": "ok"}

    def test_ready_after_preload(self, make_client: ClientFactory) -> None:
        client = make_client()
        body = wait_ready(client)
        assert body == {"ready": True, "languages": {"xx": "ready"}}

    def test_not_ready_when_load_fails(self, make_client: ClientFactory) -> None:
        client = make_client([language("xx", engine_options={"fail_load": True})])
        wait_ready(client, timeout=0.5)
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["languages"] == {"xx": "failed"}

    def test_lazy_mode_ready_before_load(self, make_client: ClientFactory) -> None:
        client = make_client(preload=False)
        assert client.get("/ready").json() == {"ready": True, "languages": {"xx": "not_loaded"}}


class TestLanguages:
    def test_list_reflects_configuration(self, make_client: ClientFactory) -> None:
        client = make_client(
            [language("xx"), language("yy", engine_options={"structures": ["dependency"]})]
        )
        langs = {lang["code"]: lang for lang in client.get("/api/v1/languages").json()["languages"]}
        assert set(langs) == {"xx", "yy"}
        assert langs["xx"]["structures"] == ["constituency", "dependency"]
        assert langs["yy"]["structures"] == ["dependency"]
        caps = {c["capability"]: c for c in langs["xx"]["capabilities"]}
        assert caps["dependency"]["scheme"] == {
            "id": "test-dep",
            "name": "Test dependency scheme",
            "url": None,
        }
        assert caps["tokenization"]["scheme"] is None

    def test_detail_by_alias(self, make_client: ClientFactory) -> None:
        body = make_client().get("/api/v1/languages/XXX").json()
        assert body["code"] == "xx"
        assert body["samples"] == [{"text": "a b c", "note": "sample"}]
        assert body["limits"] == {"max_chars": 300, "max_words": 40, "max_sentences": 1}
        assert body["engine"].endswith("WhitespaceTestEngine")

    def test_unknown_language(self, make_client: ClientFactory) -> None:
        response = make_client().get("/api/v1/languages/zz")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unsupported_language"
        assert response.json()["error"]["details"] == {"supported": ["xx"]}


class TestParse:
    def test_all_supported_structures_by_default(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "the cat sleeps")
        assert response.status_code == 200
        body = response.json()
        assert body["language"] == {"code": "xx", "name": "Test xx"}
        sentence = body["sentences"][0]
        assert [t["form"] for t in sentence["tokens"]] == ["the", "cat", "sleeps"]
        assert sentence["dependency"]["scheme"] == "test-dep"
        assert sentence["constituency"]["scheme"] == "test-con"
        prov = body["provenance"]
        assert prov["engine"] == "whitespace-test"
        assert prov["model"] == "test:whitespace"
        assert prov["cached"] is False
        assert "confidence" not in str(body)

    def test_requested_structure_only(self, make_client: ClientFactory) -> None:
        body = parse(make_client(), "a b", structures=["dependency"]).json()
        assert body["sentences"][0]["constituency"] is None
        assert {c["capability"] for c in body["provenance"]["components"]} == {
            "tokenization",
            "dependency",
        }

    def test_unsupported_structure_is_an_error_not_a_fallback(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client([language("xx", engine_options={"structures": ["dependency"]})])
        response = parse(client, "a b", structures=["constituency"])
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "unsupported_structure"
        assert error["details"] == {"supported": ["dependency"]}

    def test_unknown_language(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "a b", lang="fil")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unsupported_language"

    def test_text_is_nfc_normalized(self, make_client: ClientFactory) -> None:
        body = parse(make_client(), "Cafe\u0301 ok").json()
        assert body["text"] == "Caf\u00e9 ok"
        assert body["sentences"][0]["tokens"][0]["form"] == "Caf\u00e9"

    def test_empty_text(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "   ")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "empty_text"

    def test_text_too_long_uses_language_limit(self, make_client: ClientFactory) -> None:
        client = make_client([language("xx", limits={"max_chars": 10})])
        response = parse(client, "a" * 11)
        assert response.json()["error"]["code"] == "text_too_long"

    def test_too_many_sentences(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "a b | c d")
        assert response.status_code == 422
        assert response.json()["error"]["details"] == {"sentences": 2, "max_sentences": 1}

    def test_too_many_words(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), " ".join(["w"] * 41))
        assert response.json()["error"]["code"] == "too_many_words"

    def test_malformed_request_does_not_echo_input(self, make_client: ClientFactory) -> None:
        response = make_client().post(
            "/api/v1/parse", json={"language": "xx", "text": "secret", "extra": 1}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        assert "secret" not in response.text

    def test_invalid_structure_name(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "a", structures=["semantic"])
        assert response.json()["error"]["code"] == "invalid_request"

    def test_body_too_large(self, make_client: ClientFactory) -> None:
        client = make_client(max_body_bytes=1024)
        response = parse(client, "a" * 2000)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "payload_too_large"

    def test_engine_failure(self, make_client: ClientFactory) -> None:
        client = make_client([language("xx", engine_options={"fail_analyze": True})])
        response = parse(client, "a b")
        assert response.status_code == 500
        assert response.json()["error"] == {
            "code": "engine_failure",
            "message": "The analyzer failed on this input.",
        }

    def test_invalid_engine_output_is_rejected_not_repaired(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client(
            [language("xx", engine_options={"structures": ["dependency"], "invalid_output": True})]
        )
        response = parse(client, "a b c")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "invalid_engine_output"

    def test_model_unavailable_after_failed_load(self, make_client: ClientFactory) -> None:
        client = make_client([language("xx", engine_options={"fail_load": True})])
        wait_ready(client, timeout=0.5)
        response = parse(client, "a b")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "model_unavailable"

    def test_lazy_load_on_first_request(self, make_client: ClientFactory) -> None:
        client = make_client(preload=False)
        assert parse(client, "a b").status_code == 200
        assert client.get("/ready").json()["languages"] == {"xx": "ready"}

    def test_results_are_cached(self, make_client: ClientFactory) -> None:
        client = make_client()
        first = parse(client, "a b").json()
        second = parse(client, "a b").json()
        assert WhitespaceTestEngine.calls == 1
        assert second["provenance"]["cached"] is True
        assert first["sentences"] == second["sentences"]
        parse(client, "a b", structures=["dependency"])  # different key
        assert WhitespaceTestEngine.calls == 2

    def test_timeout(self, make_client: ClientFactory) -> None:
        client = make_client(
            [language("xx", engine_options={"delay_s": 0.5})], analysis_timeout_s=0.05
        )
        response = parse(client, "a b")
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "analysis_timeout"

    def test_overload_returns_503_with_retry_after(self, make_client: ClientFactory) -> None:
        client = make_client(max_queue=1)
        wait_ready(client)
        WhitespaceTestEngine.gate = threading.Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            blocked = pool.submit(parse, client, "first request")
            # Wait until the first request occupies the only queue slot.
            for _ in range(500):
                if WhitespaceTestEngine.calls:
                    break
                threading.Event().wait(0.01)
            response = parse(client, "second request")
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "overloaded"
            assert response.headers["retry-after"] == "5"
            WhitespaceTestEngine.gate.set()
            assert blocked.result().status_code == 200

    def test_rate_limit(self, make_client: ClientFactory) -> None:
        client = make_client(rate_limit_per_minute=60, rate_limit_burst=2)
        assert parse(client, "a").status_code == 200
        assert parse(client, "b").status_code == 200
        response = parse(client, "c")
        assert response.status_code == 429
        assert "retry-after" in response.headers

    def test_cors_allows_configured_origin_only(self, make_client: ClientFactory) -> None:
        client = make_client(cors_origins=["https://syntaxlab.example"])
        ok = client.options(
            "/api/v1/parse",
            headers={
                "Origin": "https://syntaxlab.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert ok.headers.get("access-control-allow-origin") == "https://syntaxlab.example"
        denied = client.options(
            "/api/v1/parse",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in denied.headers


def test_openapi_documents_error_schema(make_client: ClientFactory) -> None:
    schema = make_client().get("/openapi.json").json()
    responses = schema["paths"]["/api/v1/parse"]["post"]["responses"]
    assert {"200", "404", "422", "429", "503"} <= set(responses)
    assert "ErrorResponse" in schema["components"]["schemas"]


class TestSchemes:
    def test_glossary_served_for_declared_scheme(
        self, make_client: ClientFactory, tmp_path: Path
    ) -> None:
        directory = tmp_path / "glossary"
        directory.mkdir()
        (directory / "test-dep.yaml").write_text(
            "id: test-dep\nkind: dependency\nentries:\n"
            "  dep: {name: dependency, definition: A test relation.}\n",
            encoding="utf-8",
        )
        body = make_client(glossary_dir=directory).get("/api/v1/schemes/test-dep").json()
        assert body["name"] == "Test dependency scheme"
        assert body["entries"]["dep"]["definition"] == "A test relation."
        assert body["entries"]["dep"]["values"] == {}

    def test_scheme_without_glossary(self, make_client: ClientFactory, tmp_path: Path) -> None:
        response = make_client(glossary_dir=tmp_path).get("/api/v1/schemes/test-con")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unknown_scheme"

    def test_undeclared_scheme_never_read_from_disk(self, make_client: ClientFactory) -> None:
        response = make_client().get("/api/v1/schemes/..%2F..%2Fconfig%2Flanguages")
        assert response.status_code == 404
