from __future__ import annotations

from tests.conftest import ClientFactory


def test_list_and_detail_without_answer_key(make_client: ClientFactory) -> None:
    client = make_client()
    exercises = client.get("/api/v1/learning/exercises").json()["exercises"]
    assert {e["kind"] for e in exercises} == {"pos", "dependency", "constituency"}
    pos_id = next(e["id"] for e in exercises if e["kind"] == "pos")
    detail = client.get(f"/api/v1/learning/exercises/{pos_id}").json()
    assert detail["answer_key"]["kind"] == "gold_annotation"
    assert detail["answer_key"]["treebank"] == "UD_English-EWT"
    assert all(set(t) == {"id", "form"} for t in detail["tokens"])  # no gold tags or heads
    assert "upos" not in str(detail["tokens"])


def test_constituency_detail(make_client: ClientFactory) -> None:
    detail = make_client().get("/api/v1/learning/exercises/grammar-02").json()
    assert detail["answer_key"]["kind"] == "grammar_parses"
    assert detail["grammar_name"] == "Prepositional-phrase attachment"
    assert [o["value"] for o in detail["options"]][:3] == ["S", "NP", "VP"]
    assert [t["form"] for t in detail["tokens"]][-1] == "telescope"


def test_check_pos(make_client: ClientFactory) -> None:
    client = make_client()
    detail = client.get("/api/v1/learning/exercises/ud-en-pos-01").json()
    tags = ["NOUN"] * len(detail["tokens"])
    body = client.post(
        "/api/v1/learning/exercises/ud-en-pos-01/check",
        json={"answer": {"kind": "pos", "tags": tags}},
    ).json()
    fb = body["feedback"]
    assert fb["kind"] == "pos"
    assert fb["total"] == len(tags)
    assert all(i["expected"] for i in fb["items"])


def test_check_constituency_both_readings(make_client: ClientFactory) -> None:
    np_attach = [
        ("S", 0, 7),
        ("NP", 0, 1),
        ("Pronoun", 0, 1),
        ("VP", 1, 7),
        ("V", 1, 2),
        ("NP", 2, 7),
        ("NP", 2, 4),
        ("Det", 2, 3),
        ("N", 3, 4),
        ("PP", 4, 7),
        ("P", 4, 5),
        ("NP", 5, 7),
        ("Det", 5, 6),
        ("N", 6, 7),
    ]
    body = (
        make_client()
        .post(
            "/api/v1/learning/exercises/grammar-02/check",
            json={
                "answer": {
                    "kind": "constituency",
                    "constituents": [
                        {"label": label, "start": s, "end": e} for label, s, e in np_attach
                    ],
                }
            },
        )
        .json()
    )
    fb = body["feedback"]
    assert fb["status"] == "matches"
    assert fb["parse_count"] == 2
    assert fb["reference"]["symbol"] == "S"


def test_answer_kind_must_match(make_client: ClientFactory) -> None:
    response = make_client().post(
        "/api/v1/learning/exercises/grammar-01/check",
        json={"answer": {"kind": "pos", "tags": []}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_unknown_exercise(make_client: ClientFactory) -> None:
    response = make_client().get("/api/v1/learning/exercises/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_exercise"
