"""Generic Stanza engine (https://stanfordnlp.github.io/stanza/).

One class serves every language Stanza has models for; the language entry in
``config/languages.yaml`` selects the language, model package and processors. Supported
``engine_options``:

    lang:        Stanza language code (defaults to the SyntaxLab language code)
    package:     Stanza package name, e.g. "default" (default) or "default_accurate"
    processors:  list of Stanza processors (default: tokenize, mwt, pos, lemma, depparse,
                 constituency). Capabilities are derived from this list, so a language whose
                 Stanza models lack e.g. constituency simply omits that processor.
    pipeline_options: extra keyword arguments passed verbatim to ``stanza.Pipeline``.

``stanza`` and ``torch`` are imported lazily so the API can describe languages (and run its
test-suite) without them installed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar

from syntaxlab_api.engines.base import Engine, EngineConfigError, EngineContext, EngineError
from syntaxlab_api.schemas.analysis import (
    Capability,
    ConstituencyAnalysis,
    ConstituencyNode,
    DependencyAnalysis,
    DependencyArc,
    MultiwordToken,
    SentenceAnalysis,
    StructureKind,
    Token,
)

DEFAULT_PROCESSORS = ("tokenize", "mwt", "pos", "lemma", "depparse", "constituency")

# Which SyntaxLab capabilities each Stanza processor provides.
_PROCESSOR_CAPABILITIES: Mapping[str, tuple[Capability, ...]] = {
    "tokenize": (Capability.TOKENIZATION,),
    "pos": (Capability.POS, Capability.MORPHOLOGY),  # Stanza's POS tagger also predicts UFeats
    "lemma": (Capability.LEMMA,),
    "depparse": (Capability.DEPENDENCY,),
    "constituency": (Capability.CONSTITUENCY,),
}
_KNOWN_PROCESSORS = {*DEFAULT_PROCESSORS}

# Processors needed to produce each structure (Stanza runs prerequisites in pipeline order).
_STRUCTURE_PROCESSORS: Mapping[StructureKind, str] = {
    StructureKind.DEPENDENCY: "depparse",
    StructureKind.CONSTITUENCY: "constituency",
}


class StanzaEngine(Engine):
    name: ClassVar[str] = "stanza"

    def __init__(self, context: EngineContext) -> None:
        super().__init__(context)
        opts = dict(context.options)
        self.lang: str = str(opts.pop("lang", context.language))
        self.package: str = str(opts.pop("package", "default"))
        processors = opts.pop("processors", list(DEFAULT_PROCESSORS))
        if not isinstance(processors, list) or not all(isinstance(p, str) for p in processors):
            raise EngineConfigError("stanza 'processors' must be a list of strings")
        unknown = set(processors) - _KNOWN_PROCESSORS
        if unknown:
            raise EngineConfigError(f"unsupported stanza processors: {sorted(unknown)}")
        if "tokenize" not in processors:
            raise EngineConfigError("stanza 'processors' must include 'tokenize'")
        self.processors: tuple[str, ...] = tuple(processors)
        pipeline_options = opts.pop("pipeline_options", {})
        if not isinstance(pipeline_options, dict):
            raise EngineConfigError("stanza 'pipeline_options' must be a mapping")
        self.pipeline_options: dict[str, Any] = pipeline_options
        if opts:
            raise EngineConfigError(f"unknown stanza engine options: {sorted(opts)}")

        self._pipeline: Any = None
        self._components: dict[str, str] = {
            p: f"stanza/{self.lang}/{self.package}/{p}" for p in self.processors
        }

    # ------------------------------------------------------------------ metadata

    def capabilities(self) -> Mapping[Capability, str]:
        caps: dict[Capability, str] = {}
        for processor in self.processors:
            for cap in _PROCESSOR_CAPABILITIES.get(processor, ()):
                caps[cap] = self._components[processor]
        return caps

    @property
    def engine_version(self) -> str | None:
        try:
            import stanza
        except ImportError:
            return None
        return str(stanza.__version__)

    @property
    def model_id(self) -> str:
        return f"stanza:{self.lang}:{self.package}"

    # ------------------------------------------------------------------ lifecycle

    def _model_dir(self) -> str | None:
        return str(self.context.models_dir / "stanza") if self.context.models_dir else None

    def download(self) -> None:
        stanza = _import_stanza()
        kwargs: dict[str, Any] = {"package": self.package, "processors": ",".join(self.processors)}
        if (model_dir := self._model_dir()) is not None:
            kwargs["model_dir"] = model_dir
        stanza.download(self.lang, **kwargs)

    def load(self) -> None:
        stanza = _import_stanza()
        try:
            import torch

            torch.set_num_threads(max(1, self.context.cpu_threads))
        except ImportError:  # pragma: no cover - torch is a hard dependency of stanza
            pass
        kwargs: dict[str, Any] = {
            "lang": self.lang,
            "package": self.package,
            "processors": ",".join(self.processors),
            "download_method": None,  # never download during serving; see download()
            "use_gpu": False,
            "logging_level": "WARN",
            **self.pipeline_options,
        }
        if (model_dir := self._model_dir()) is not None:
            kwargs["dir"] = model_dir
        try:
            self._pipeline = stanza.Pipeline(**kwargs)
        except Exception as exc:  # stanza raises many types; normalize them
            raise EngineError(
                f"could not load Stanza models for {self.lang!r}/{self.package!r}. "
                "Run `syntaxlab-api download-models` first."
            ) from exc
        # Record the concrete model file behind each processor (e.g. "ptb3-revised_charlm").
        for processor in self.processors:
            proc = self._pipeline.processors.get(processor)
            model_path = getattr(proc, "config", {}).get("model_path") if proc else None
            if model_path:
                self._components[processor] = (
                    f"stanza/{self.lang}/{processor}/{Path(str(model_path)).stem}"
                )

    def close(self) -> None:
        self._pipeline = None

    # ------------------------------------------------------------------ analysis

    def analyze(self, text: str, structures: frozenset[StructureKind]) -> list[SentenceAnalysis]:
        if self._pipeline is None:
            raise EngineError("engine not loaded")
        wanted = [
            p
            for p in self.processors
            if p not in _STRUCTURE_PROCESSORS.values()
            or any(_STRUCTURE_PROCESSORS[s] == p for s in structures)
        ]
        try:
            doc = self._pipeline(text, processors=",".join(wanted))
        except Exception as exc:
            raise EngineError("Stanza failed while analyzing the text") from exc
        dep_scheme = (
            self.scheme_for(Capability.DEPENDENCY)
            if (StructureKind.DEPENDENCY in structures)
            else None
        )
        con_scheme = (
            self.scheme_for(Capability.CONSTITUENCY)
            if (StructureKind.CONSTITUENCY in structures)
            else None
        )
        return [
            normalize_sentence(s, dependency_scheme=dep_scheme, constituency_scheme=con_scheme)
            for s in doc.sentences
        ]


def _import_stanza() -> Any:
    try:
        import stanza
    except ImportError as exc:
        raise EngineError(
            "the 'stanza' engine needs the optional dependency: "
            "install with `uv sync --extra stanza`"
        ) from exc
    return stanza


# ---------------------------------------------------------------------- normalization


def parse_feats(raw: str | None) -> dict[str, str]:
    """Parse a CoNLL-U FEATS string ("A=B|C=D") into a dict. ``None``/"_" -> {}."""
    if not raw or raw == "_":
        return {}
    feats: dict[str, str] = {}
    for item in raw.split("|"):
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise EngineError(f"malformed feature {item!r}")
        feats[key] = value
    return feats


def normalize_sentence(
    sentence: Any,
    *,
    dependency_scheme: str | None,
    constituency_scheme: str | None,
) -> SentenceAnalysis:
    """Convert one ``stanza.models.common.doc.Sentence`` to the SyntaxLab schema.

    Values are copied as produced by Stanza. Nothing is relabelled or re-attached.
    """
    words = list(sentence.words)
    tokens = [
        Token(
            id=w.id,
            form=w.text,
            lemma=w.lemma,
            upos=w.upos,
            xpos=w.xpos,
            feats=parse_feats(w.feats),
            start_char=w.start_char,
            end_char=w.end_char,
        )
        for w in words
    ]

    mwts = [
        MultiwordToken(
            first=t.id[0],
            last=t.id[-1],
            form=t.text,
            start_char=t.start_char,
            end_char=t.end_char,
        )
        for t in sentence.tokens
        if len(t.id) > 1
    ]

    dependency = None
    if dependency_scheme is not None:
        if any(w.head is None or w.deprel is None for w in words):
            raise EngineError("dependency parse requested but Stanza returned no heads")
        dependency = DependencyAnalysis(
            scheme=dependency_scheme,
            arcs=[DependencyArc(dependent=w.id, head=w.head, relation=w.deprel) for w in words],
        )

    constituency = None
    if constituency_scheme is not None:
        tree = getattr(sentence, "constituency", None)
        if tree is None:
            raise EngineError("constituency parse requested but Stanza returned no tree")
        constituency = convert_tree(tree, [w.text for w in words], scheme=constituency_scheme)

    start = tokens[0].start_char if tokens else None
    end = tokens[-1].end_char if tokens else None
    return SentenceAnalysis(
        text=sentence.text,
        start_char=start,
        end_char=end,
        tokens=tokens,
        multiword_tokens=mwts,
        dependency=dependency,
        constituency=constituency,
    )


def convert_tree(tree: Any, word_forms: Sequence[str], *, scheme: str) -> ConstituencyAnalysis:
    """Convert a Stanza constituency ``Tree`` to flat nodes with ids and spans.

    Each leaf must be the only child of a pre-terminal and must match the corresponding
    syntactic word *exactly*; otherwise the tree and the token layer disagree, and we raise
    rather than guess an alignment.
    """
    nodes: list[ConstituencyNode] = []
    next_word = 0
    counter = 0

    def visit(node: Any) -> tuple[str, tuple[int, int]]:
        nonlocal next_word, counter
        node_id = f"n{counter}"
        counter += 1
        slot = len(nodes)
        nodes.append(ConstituencyNode(id=node_id, label="?", span=(0, 0)))  # placeholder

        children = list(node.children)
        if len(children) == 1 and not children[0].children:  # pre-terminal over a leaf
            leaf_text = children[0].label
            if next_word >= len(word_forms):
                raise EngineError("constituency tree has more leaves than the sentence has words")
            if leaf_text != word_forms[next_word]:
                raise EngineError(
                    f"constituency leaf {leaf_text!r} does not match word "
                    f"{next_word + 1} {word_forms[next_word]!r}"
                )
            next_word += 1
            span = (next_word, next_word)
            nodes[slot] = ConstituencyNode(
                id=node_id, label=node.label, token_id=next_word, span=span
            )
            return node_id, span

        if not children:
            raise EngineError(f"constituency node {node.label!r} has no children")
        for child in children:
            if not child.children:
                raise EngineError(f"leaf {child.label!r} is not under a pre-terminal")
        visited = [visit(c) for c in children]
        span = (visited[0][1][0], visited[-1][1][1])
        nodes[slot] = ConstituencyNode(
            id=node_id, label=node.label, children=[cid for cid, _ in visited], span=span
        )
        return node_id, span

    root_id, _ = visit(tree)
    if next_word != len(word_forms):
        raise EngineError(
            f"constituency tree covers {next_word} words but the sentence has {len(word_forms)}"
        )
    return ConstituencyAnalysis(scheme=scheme, root=root_id, nodes=nodes)
