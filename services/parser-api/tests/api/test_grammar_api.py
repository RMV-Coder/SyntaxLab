"""HTTP tests for the Algorithm Lab endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import ClientFactory

PP_GRAMMAR = """
S -> NP VP
NP -> "I" | Det N | NP PP
VP -> V NP | VP PP
PP -> P NP
Det -> "the" | "a"
N -> "man" | "telescope"
V -> "saw"
P -> "with"
"""


def parse(client: TestClient, sentence: str, grammar: str = PP_GRAMMAR, **extra: object) -> object:
    return client.post(
        "/api/v1/grammar/parse", json={"grammar": grammar, "sentence": sentence, **extra}
    )


class TestPresets:
    def test_list_and_detail(self, make_client: ClientFactory) -> None:
        client = make_client()
        presets = client.get("/api/v1/grammar/presets").json()["presets"]
        ids = [p["id"] for p in presets]
        assert ids[0] == "pp-attachment"  # explicit `order` in the data files
        assert {"pp-attachment", "coordination", "optional-elements", "arithmetic"} <= set(ids)
        detail = client.get("/api/v1/grammar/presets/pp-attachment").json()
        assert "NP PP" in detail["grammar"]
        assert detail["examples"][0]["expect"] == {"accepted": True, "parses": 2}

    def test_unknown_preset(self, make_client: ClientFactory) -> None:
        response = make_client().get("/api/v1/grammar/presets/nope")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unknown_grammar"


class TestValidate:
    def test_valid(self, make_client: ClientFactory) -> None:
        body = make_client().post("/api/v1/grammar/validate", json={"grammar": PP_GRAMMAR}).json()
        assert body["valid"] is True
        assert body["grammar"]["start"] == "S"
        assert body["grammar"]["rules"][0]["text"] == "γ → S"
        assert body["diagnostics"] == []

    def test_errors_and_warnings_with_lines(self, make_client: ClientFactory) -> None:
        body = (
            make_client()
            .post("/api/v1/grammar/validate", json={"grammar": 'S -> NP\nX -> "x"'})
            .json()
        )
        assert body["valid"] is False
        assert {(d["code"], d["line"]) for d in body["diagnostics"]} >= {("undefined_symbol", 1)}
        assert body["grammar"] is not None  # syntactically fine, so it is still described

    def test_syntax_error_has_no_summary(self, make_client: ClientFactory) -> None:
        body = make_client().post("/api/v1/grammar/validate", json={"grammar": "S NP"}).json()
        assert body == {
            "valid": False,
            "diagnostics": [
                {
                    "severity": "error",
                    "code": "missing_arrow",
                    "message": "Expected a rule like “NP -> Det N”.",
                    "line": 1,
                }
            ],
            "grammar": None,
        }


class TestParse:
    def test_ambiguous_sentence_returns_trace_chart_and_both_trees(
        self, make_client: ClientFactory
    ) -> None:
        body = parse(make_client(), "I saw the man with a telescope").json()
        assert body["accepted"] is True
        assert body["tree_count"] == 2
        assert body["tree_count_capped"] is False
        assert len(body["trees"]) == 2
        assert body["tokens"] == ["I", "saw", "the", "man", "with", "a", "telescope"]
        assert len(body["chart"]) == 8
        assert body["trace"][0]["kind"] == "init"
        assert body["trace"][-1]["kind"] == "accept"
        assert body["trace_truncated"] is False
        tree = body["trees"][0]
        assert (tree["symbol"], tree["kind"], tree["start"], tree["end"]) == (
            "S",
            "nonterminal",
            0,
            7,
        )

    def test_rejected_sentence_reports_unknown_words(self, make_client: ClientFactory) -> None:
        body = parse(make_client(), "I saw the dog").json()
        assert body["accepted"] is False
        assert body["tree_count"] == 0
        assert body["trees"] == []
        assert body["unknown_tokens"] == [3]
        assert body["trace"][-1]["kind"] == "reject"

    def test_max_trees_caps_enumeration_not_count(self, make_client: ClientFactory) -> None:
        body = parse(
            make_client(), " + ".join(["n"] * 8), grammar='E -> E "+" E | "n"', max_trees=3
        ).json()
        assert body["tree_count"] == 429  # Catalan C7
        assert len(body["trees"]) == 3

    def test_invalid_grammar_is_refused_with_diagnostics(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "a", grammar='S -> S | "a"')
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_grammar"
        assert error["details"]["diagnostics"][0]["code"] == "cyclic_grammar"

    def test_too_many_words(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), " ".join(["the"] * 21))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "too_many_words"

    def test_blank_sentence(self, make_client: ClientFactory) -> None:
        response = parse(make_client(), "   ")
        assert response.json()["error"]["code"] == "empty_text"

    def test_grammar_size_cap(self, make_client: ClientFactory) -> None:
        padding = "# padding\n" * 1_300
        grammar = f'S -> "a"\n{padding}'  # > 12,000 characters but < 16 KB body
        response = parse(make_client(), "a", grammar=grammar)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
