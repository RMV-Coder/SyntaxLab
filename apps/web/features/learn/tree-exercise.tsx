"use client";

import { ArrowDown, ArrowUp, Trash2, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api/client";
import type { ConstituencyFeedback, DerivationTree, ExerciseDetail } from "@/lib/api/types";
import { derivationBrackets, layoutDerivation } from "@/lib/syntax/derivation-layout";
import { cn } from "@/lib/utils";

import { useDiagramFonts, useMeasure } from "../analyzer/hooks";
import { ZoomableSvg } from "../analyzer/zoomable-svg";
import { DerivationDiagram } from "../lab/derivation-diagram";
import { constituentMessage, constituentText, problemMessage, treeSummary } from "./feedback-text";
import { recordProgress } from "./progress";
import { AnswerKeyNote, CheckBar, ScoreBanner, selectClass } from "./shared";
import {
  addConstituent,
  chainOf,
  isComplete,
  moveInChain,
  outline,
  previewTree,
  relabel,
  removeConstituent,
  type Constituent,
} from "./tree-builder-model";

function TreeView({ tree, label }: { tree: DerivationTree; label: string }) {
  const { fonts, ready } = useDiagramFonts();
  const measure = useMeasure(fonts, ready);
  const layout = useMemo(() => layoutDerivation(tree, measure), [tree, measure]);
  return (
    <div className="h-72 rounded-md border border-rule bg-sheet" data-testid="tree-preview">
      <ZoomableSvg width={layout.width} height={layout.height} label={label}>
        <DerivationDiagram layout={layout} fonts={fonts} selectedId={null} onSelect={() => undefined} />
      </ZoomableSvg>
    </div>
  );
}

export function TreeExercise({ exercise }: { exercise: ExerciseDetail }) {
  const words = exercise.tokens.map((t) => t.form);
  const [history, setHistory] = useState<Constituent[][]>([[]]);
  const list = history[history.length - 1];
  const [anchor, setAnchor] = useState<number | null>(null);
  const [span, setSpan] = useState<[number, number] | null>(null);
  const [label, setLabel] = useState(exercise.options[0]?.value ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<ConstituencyFeedback | null>(null);
  const [showReference, setShowReference] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const commit = (next: Constituent[]) => {
    setHistory((h) => [...h, next]);
    setFeedback(null);
    setShowReference(false);
  };

  const pickWord = (i: number) => {
    setMessage(null);
    if (anchor === null) {
      setAnchor(i);
      setSpan([i, i + 1]);
    } else {
      setSpan([Math.min(anchor, i), Math.max(anchor, i) + 1]);
      setAnchor(null);
    }
  };

  const add = () => {
    if (!span || !label) return;
    const result = addConstituent(list, label, span[0], span[1]);
    if (!result.ok) {
      setMessage(
        result.reason === "duplicate"
          ? `${constituentText(result.conflict, words)} already exists.`
          : `That would cross ${constituentText(result.conflict, words)}. Constituents must nest inside each other.`,
      );
      return;
    }
    commit(result.list);
    setMessage(null);
    setSpan(null);
    setAnchor(null);
  };

  const check = () => {
    setBusy(true);
    setError(null);
    api
      .checkAnswer(exercise.id, {
        answer: {
          kind: "constituency",
          constituents: list.map(({ label: l, start, end }) => ({ label: l, start, end })),
        },
      })
      .then((r) => {
        if (r.feedback.kind !== "constituency") return;
        const f = r.feedback;
        setFeedback(f);
        const score = f.precision + f.recall ? (2 * f.precision * f.recall) / (f.precision + f.recall) : 0;
        recordProgress(exercise.id, f.status === "matches" ? 1 : score, f.status === "matches");
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Checking failed."))
      .finally(() => setBusy(false));
  };

  const tree = useMemo(() => previewTree(list, words), [list, words]);
  const summary = feedback ? treeSummary(feedback) : null;
  const statusOf = (c: Constituent) =>
    feedback?.constituents.find((f) => f.label === c.label && f.start === c.start && f.end === c.end && f.status !== "missing")
      ?.status;

  return (
    <div className="space-y-6">
      <section aria-labelledby="pick-heading" className="space-y-3">
        <h2 id="pick-heading" className="text-sm font-medium">
          1. Select words: the first, then the last (or the same word again)
        </h2>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Words of the sentence">
          {words.map((w, i) => {
            const inSpan = span !== null && i >= span[0] && i < span[1];
            return (
              <button
                key={i}
                type="button"
                aria-pressed={inSpan}
                onClick={() => pickWord(i)}
                className={cn(
                  "rounded-md border px-2.5 py-1.5 font-data text-lg",
                  inSpan ? "border-ink bg-highlight text-ink" : "border-rule bg-sheet text-ink hover:border-rule-strong",
                  anchor === i && "ring-2 ring-ink ring-offset-1",
                )}
              >
                {w}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="mb-1 block font-medium">2. Category</span>
            <select
              className={cn(selectClass, "w-36")}
              value={label}
              aria-label="Category"
              onChange={(e) => setLabel(e.target.value)}
            >
              {exercise.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.value}
                </option>
              ))}
            </select>
          </label>
          <Button onClick={add} disabled={!span || !label}>
            {span ? `Add ${label} over “${words.slice(span[0], span[1]).join(" ")}”` : "Add constituent"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setHistory((h) => (h.length > 1 ? h.slice(0, -1) : h))}
            disabled={history.length <= 1}
          >
            <Undo2 aria-hidden />
            Undo
          </Button>
        </div>
        {message ? (
          <p role="alert" className="text-sm text-destructive">
            {message}
          </p>
        ) : null}
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section aria-labelledby="list-heading" className="space-y-2">
          <h2 id="list-heading" className="text-sm font-medium">
            Your constituents ({list.length})
          </h2>
          {list.length === 0 ? (
            <p className="text-sm text-graphite">None yet. A good start is a category for each word.</p>
          ) : (
            <ul className="space-y-1">
              {outline(list).map(({ constituent: c, depth }) => {
                const chain = chainOf(list, c.id);
                const position = chain.findIndex((x) => x.id === c.id);
                const status = statusOf(c);
                return (
                  <li key={c.id} className="flex items-center gap-1.5" style={{ paddingLeft: `${depth * 0.9}rem` }}>
                    <select
                      className="rounded border border-input bg-sheet px-1 py-0.5 font-data text-sm font-bold"
                      value={c.label}
                      aria-label={`Category of “${words.slice(c.start, c.end).join(" ")}”`}
                      onChange={(e) => commit(relabel(list, c.id, e.target.value))}
                    >
                      {exercise.options.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.value}
                        </option>
                      ))}
                    </select>
                    <span className="min-w-0 flex-1 truncate font-data text-sm text-ink-soft">
                      {words.slice(c.start, c.end).join(" ")}
                    </span>
                    {status ? (
                      <span
                        className={cn(
                          "text-xs",
                          status === "correct" ? "text-pos-modifier" : status === "other_reading" ? "text-pos-function" : "text-destructive",
                        )}
                      >
                        {status === "correct" ? "✓" : status === "other_reading" ? "other reading" : "not allowed here"}
                      </span>
                    ) : null}
                    {chain.length > 1 ? (
                      <>
                        <Button variant="ghost" size="icon" className="size-7" aria-label={`Move ${c.label} up in its chain`} disabled={position === 0} onClick={() => commit(moveInChain(list, c.id, "up"))}>
                          <ArrowUp aria-hidden />
                        </Button>
                        <Button variant="ghost" size="icon" className="size-7" aria-label={`Move ${c.label} down in its chain`} disabled={position === chain.length - 1} onClick={() => commit(moveInChain(list, c.id, "down"))}>
                          <ArrowDown aria-hidden />
                        </Button>
                      </>
                    ) : null}
                    <Button variant="ghost" size="icon" className="size-7" aria-label={`Remove ${c.label} over “${words.slice(c.start, c.end).join(" ")}”`} onClick={() => commit(removeConstituent(list, c.id))}>
                      <Trash2 aria-hidden />
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <section aria-labelledby="preview-heading" className="space-y-2">
          <h2 id="preview-heading" className="text-sm font-medium">
            Your tree
          </h2>
          <TreeView tree={tree} label="Your tree" />
          <p className="break-words font-data text-xs text-graphite">{derivationBrackets(tree)}</p>
        </section>
      </div>

      <CheckBar
        busy={busy}
        disabled={list.length === 0}
        checked={feedback != null}
        onCheck={check}
        onReset={() => commit([])}
        hint={isComplete(list, words.length) ? null : "The tree needs a category over the whole sentence."}
      />
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {feedback && summary ? (
        <ScoreBanner solved={summary.solved} title={summary.title} body={summary.body}>
          {feedback.status !== "matches" ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-soft">
              {feedback.problems.map((p, i) => (
                <li key={`p${i}`}>{problemMessage(p)}</li>
              ))}
              {feedback.constituents
                .filter((c) => c.status !== "correct")
                .map((c, i) => (
                  <li key={`c${i}`}>{constituentMessage(c, words)}</li>
                ))}
            </ul>
          ) : null}
          {feedback.reference ? (
            <Button variant="outline" size="sm" className="mt-3" onClick={() => setShowReference((s) => !s)}>
              {showReference ? "Hide" : feedback.status === "matches" ? "Compare with the grammar's tree" : "Show a correct tree"}
            </Button>
          ) : null}
        </ScoreBanner>
      ) : null}
      {feedback?.reference && showReference ? (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">
            {feedback.parse_count > 1 ? `Parse ${feedback.closest_parse} of ${feedback.parse_count}` : "The grammar's tree"}
          </h2>
          <TreeView tree={feedback.reference} label="A correct tree" />
        </section>
      ) : null}

      <details className="text-sm">
        <summary className="cursor-pointer font-medium">The grammar: {exercise.grammar_name}</summary>
        <pre className="mt-2 overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">{exercise.grammar}</pre>
      </details>
      <AnswerKeyNote exercise={exercise} />
    </div>
  );
}
