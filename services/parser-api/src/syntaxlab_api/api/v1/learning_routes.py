"""Learning exercises: list, fetch (without answers), and check an answer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from syntaxlab_api import errors
from syntaxlab_api.api.v1.routes import ERROR_RESPONSES, rate_limited
from syntaxlab_api.glossary import Glossary
from syntaxlab_api.grammar.grammar import compile_grammar, tokenize
from syntaxlab_api.grammar.presets import GrammarPreset
from syntaxlab_api.learning import checking
from syntaxlab_api.learning.exercises import (
    ConstituencyExercise,
    DependencyExercise,
    PosExercise,
)
from syntaxlab_api.schemas.learning import (
    AnswerKeySource,
    CheckRequest,
    CheckResponse,
    ConstituencyAnswer,
    ConstituencyFeedback,
    DependencyAnswer,
    DependencyFeedback,
    ExerciseDetail,
    ExerciseList,
    ExerciseSummary,
    ExerciseToken,
    LabelOption,
    PosAnswer,
    PosFeedback,
)

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])

AnyExercise = PosExercise | DependencyExercise | ConstituencyExercise

INSTRUCTIONS = {
    "pos": "Choose the part of speech of every word, using the Universal Dependencies tag set.",
    "dependency": (
        "For every word, choose the word it depends on (its head) and the relation. "
        "Exactly one word is the root of the sentence."
    ),
    "constituency": "Build the phrase-structure tree the grammar assigns to the sentence.",
}


def _exercises(request: Request) -> dict[str, AnyExercise]:
    exercises: dict[str, AnyExercise] = request.app.state.exercises
    return exercises


def _get(request: Request, exercise_id: str) -> AnyExercise:
    exercise = _exercises(request).get(exercise_id)
    if exercise is None:
        raise errors.UnknownExercise(f"No exercise {exercise_id!r}.")
    return exercise


def _preset(request: Request, exercise: ConstituencyExercise) -> GrammarPreset:
    presets: dict[str, GrammarPreset] = request.app.state.grammar_presets
    return presets[exercise.grammar]


def _summary(exercise: AnyExercise) -> ExerciseSummary:
    return ExerciseSummary(
        id=exercise.id,
        kind=exercise.kind,
        title=exercise.title,
        difficulty=exercise.difficulty,
        language=None if isinstance(exercise, ConstituencyExercise) else exercise.language,
    )


def _name(glossary: Glossary | None, label: str) -> str | None:
    if glossary is None:
        return None
    entry = glossary.entries.get(label) or glossary.entries.get(label.split(":", 1)[0])
    return entry.name if entry else None


@router.get("/exercises", response_model=ExerciseList, summary="All exercises")
def list_exercises(request: Request) -> ExerciseList:
    return ExerciseList(exercises=[_summary(e) for e in _exercises(request).values()])


@router.get(
    "/exercises/{exercise_id}",
    response_model=ExerciseDetail,
    responses={404: ERROR_RESPONSES[404]},
    summary="One exercise, without its answer key",
)
def get_exercise(exercise_id: str, request: Request) -> ExerciseDetail:
    exercise = _get(request, exercise_id)
    glossaries: dict[str, Glossary] = request.app.state.glossaries
    summary = _summary(exercise).model_dump()

    if isinstance(exercise, ConstituencyExercise):
        preset = _preset(request, exercise)
        grammar, _ = compile_grammar(preset.grammar)
        assert grammar is not None
        return ExerciseDetail(
            **summary,
            instructions=exercise.instructions or INSTRUCTIONS["constituency"],
            tokens=[
                ExerciseToken(id=i + 1, form=w) for i, w in enumerate(tokenize(exercise.sentence))
            ],
            options=[LabelOption(value=s, name=None) for s in grammar.nonterminals],
            grammar=preset.grammar,
            grammar_name=preset.name,
            answer_key=AnswerKeySource(
                kind="grammar_parses",
                description=(
                    f"Every parse the Earley parser finds for this sentence under the "
                    f"“{preset.name}” grammar. Any of them is accepted."
                ),
                treebank=None,
                release=None,
                sent_id=None,
                license=None,
            ),
        )

    if isinstance(exercise, PosExercise):
        upos = glossaries.get("ud-upos")
        values = list(upos.entries) if upos else sorted({t.upos for t in exercise.tokens})
        options = [LabelOption(value=v, name=_name(upos, v)) for v in values]
    else:
        ud = glossaries.get("ud-2")
        options = [LabelOption(value=r, name=_name(ud, r)) for r in exercise.relations]
    source = exercise.source
    return ExerciseDetail(
        **summary,
        instructions=INSTRUCTIONS[exercise.kind],
        tokens=[ExerciseToken(id=t.id, form=t.form) for t in exercise.tokens],
        options=options,
        grammar=None,
        grammar_name=None,
        answer_key=AnswerKeySource(
            kind="gold_annotation",
            description=(
                "The expert annotation of this sentence in the treebank. Answers are compared "
                "with that one annotation; another analysis may sometimes also be defensible."
            ),
            treebank=source.treebank,
            release=source.release,
            sent_id=source.sent_id,
            license=source.license,
        ),
    )


@router.post(
    "/exercises/{exercise_id}/check",
    response_model=CheckResponse,
    responses=ERROR_RESPONSES,
    dependencies=[Depends(rate_limited)],
    summary="Check an answer and get feedback (including the answer key)",
)
def check_answer(exercise_id: str, body: CheckRequest, request: Request) -> CheckResponse:
    exercise = _get(request, exercise_id)
    answer = body.answer
    feedback: PosFeedback | DependencyFeedback | ConstituencyFeedback
    if answer.kind != exercise.kind:
        raise errors.InvalidInput(
            f"This is a {exercise.kind} exercise, but the answer is for {answer.kind}."
        )
    if isinstance(exercise, PosExercise) and isinstance(answer, PosAnswer):
        feedback = checking.check_pos(exercise, answer)
    elif isinstance(exercise, DependencyExercise) and isinstance(answer, DependencyAnswer):
        feedback = checking.check_dependency(exercise, answer)
    elif isinstance(exercise, ConstituencyExercise) and isinstance(answer, ConstituencyAnswer):
        feedback = checking.check_constituency(exercise, _preset(request, exercise).grammar, answer)
    else:  # pragma: no cover - kinds checked above
        raise errors.InvalidInput("Answer and exercise do not match.")
    return CheckResponse(exercise=exercise.id, feedback=feedback)
