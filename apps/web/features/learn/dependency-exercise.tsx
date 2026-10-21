"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api/client";
import type {
  DependencyArc,
  DependencyFeedback,
  ExerciseDetail,
  Glossary,
  SentenceAnalysis,
} from "@/lib/api/types";
import { layoutDependency } from "@/lib/syntax/dependency-layout";
import { lookupLabel } from "@/lib/syntax/glossary";

import { ARROW_DEFS, DependencyDiagram } from "../analyzer/dependency-diagram";
import { useDiagramFonts, useMeasure } from "../analyzer/hooks";
import { highlightFor } from "../analyzer/selection";
import { ZoomableSvg } from "../analyzer/zoomable-svg";
import { recordProgress } from "./progress";
import { AnswerKeyNote, CheckBar, MarkIcon, ScoreBanner, selectClass } from "./shared";

interface Entry {
  head: string; // "" = unanswered, "0" = root
  relation: string;
}

function Graph({ exercise, arcs, label, glossary }: {
  exercise: ExerciseDetail;
  arcs: DependencyArc[];
  label: string;
  glossary?: Glossary;
}) {
  const { fonts, ready } = useDiagramFonts();
  const measure = useMeasure(fonts, ready);
  const sentence: SentenceAnalysis = useMemo(
    () => ({
      text: exercise.title,
      start_char: null,
      end_char: null,
      tokens: exercise.tokens.map((t) => ({
        id: t.id, form: t.form, lemma: null, upos: null, xpos: null, feats: {}, start_char: null, end_char: null,
      })),
      multiword_tokens: [],
      dependency: { scheme: "ud-2", arcs },
      constituency: null,
    }),
    [exercise, arcs],
  );
  const layout = useMemo(() => layoutDependency(sentence.tokens, arcs, measure), [sentence, arcs, measure]);
  return (
    <div className="h-56 rounded-md border border-rule bg-sheet" lang={exercise.language ?? undefined}>
      <ZoomableSvg width={layout.width} height={layout.height} label={label} defs={ARROW_DEFS}>
        <DependencyDiagram
          layout={layout}
          sentence={sentence}
          highlight={highlightFor(sentence, null)}
          selection={null}
          fonts={fonts}
          showLabels
          relationGlossary={glossary}
          posGlossary={undefined}
          onSelect={() => undefined}
          onHover={() => undefined}
        />
      </ZoomableSvg>
    </div>
  );
}

export function DependencyExercise({ exercise, glossary }: { exercise: ExerciseDetail; glossary?: Glossary }) {
  const empty = () => exercise.tokens.map<Entry>(() => ({ head: "", relation: "" }));
  const [entries, setEntries] = useState<Entry[]>(empty);
  const [feedback, setFeedback] = useState<DependencyFeedback | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const roots = entries.filter((e) => e.head === "0").length;
  const studentArcs: DependencyArc[] = entries.flatMap((e, i) =>
    e.head === "" ? [] : [{ dependent: i + 1, head: Number(e.head), relation: e.head === "0" ? "root" : e.relation || "?" }],
  );
  const keyArcs: DependencyArc[] = feedback
    ? feedback.items.map((i) => ({ dependent: i.token, head: i.expected_head, relation: i.expected_relation }))
    : [];

  const update = (i: number, change: Partial<Entry>) => {
    const next = [...entries];
    next[i] = { ...next[i], ...change };
    if (change.head === "0") next[i].relation = "";
    setEntries(next);
    setFeedback(null);
  };

  const check = () => {
    setBusy(true);
    setError(null);
    api
      .checkAnswer(exercise.id, {
        answer: {
          kind: "dependency",
          arcs: entries.map((e, i) => ({
            dependent: i + 1,
            head: e.head === "" ? null : Number(e.head),
            relation: e.head === "0" ? "root" : e.relation || null,
          })),
        },
      })
      .then((r) => {
        if (r.feedback.kind !== "dependency") return;
        const f = r.feedback;
        setFeedback(f);
        recordProgress(exercise.id, (f.heads_correct + f.relations_correct) / (2 * f.total), f.heads_correct === f.total && f.relations_correct === f.total);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Checking failed."))
      .finally(() => setBusy(false));
  };

  const relationName = (r: string) => lookupLabel(glossary, r).entry?.name;

  return (
    <div className="space-y-6">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] border-separate border-spacing-y-1.5 text-sm">
          <thead>
            <tr className="text-left text-xs text-graphite">
              <th scope="col" className="w-8 font-medium">#</th>
              <th scope="col" className="font-medium">Word</th>
              <th scope="col" className="font-medium">Depends on</th>
              <th scope="col" className="font-medium">Relation</th>
              {feedback ? <th scope="col" className="font-medium">Annotation</th> : null}
            </tr>
          </thead>
          <tbody>
            {exercise.tokens.map((token, i) => {
              const item = feedback?.items[i];
              return (
                <tr key={token.id} className="align-top">
                  <td className="pt-2 text-xs tabular-nums text-graphite">{token.id}</td>
                  <th scope="row" className="pr-3 pt-1 text-left font-data text-lg font-normal text-ink">
                    {token.form}
                  </th>
                  <td className="pr-2">
                    <select
                      className={selectClass}
                      value={entries[i].head}
                      aria-label={`Head of “${token.form}”`}
                      onChange={(e) => update(i, { head: e.target.value })}
                    >
                      <option value="">Choose…</option>
                      <option value="0">Nothing: it is the root</option>
                      {exercise.tokens.filter((t) => t.id !== token.id).map((t) => (
                        <option key={t.id} value={String(t.id)}>
                          {t.id} {t.form}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="pr-2">
                    <select
                      className={selectClass}
                      value={entries[i].head === "0" ? "root" : entries[i].relation}
                      disabled={entries[i].head === "0"}
                      aria-label={`Relation of “${token.form}”`}
                      onChange={(e) => update(i, { relation: e.target.value })}
                    >
                      {entries[i].head === "0" ? <option value="root">root</option> : <option value="">Choose…</option>}
                      {exercise.options.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.value}
                          {o.name ? ` (${o.name})` : ""}
                        </option>
                      ))}
                    </select>
                  </td>
                  {item ? (
                    <td className="space-y-0.5 text-xs">
                      <p>
                        <MarkIcon mark={item.head_correct ? "correct" : item.given_head == null ? "unanswered" : "incorrect"} />{" "}
                        head{" "}
                        {item.expected_head === 0
                          ? "none (root)"
                          : `${item.expected_head} ${exercise.tokens[item.expected_head - 1]?.form}`}
                      </p>
                      <p>
                        <MarkIcon mark={item.relation_status} />{" "}
                        <span className="font-medium">{item.expected_relation}</span>
                        {item.relation_status === "partial"
                          ? `: right family; the annotation uses ${item.expected_relation}`
                          : ""}
                      </p>
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-medium">Your graph</h2>
        <Graph exercise={exercise} arcs={studentArcs} label="Your dependency graph" glossary={glossary} />
      </div>

      <CheckBar
        busy={busy}
        disabled={studentArcs.length === 0}
        checked={feedback != null}
        onCheck={check}
        onReset={() => {
          setEntries(empty());
          setFeedback(null);
          setShowKey(false);
        }}
        hint={roots === 1 ? null : roots === 0 ? "No word is the root yet." : "Exactly one word should be the root."}
      />
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {feedback ? (
        <ScoreBanner
          solved={feedback.heads_correct === feedback.total && feedback.relations_correct === feedback.total}
          title={`${feedback.heads_correct} of ${feedback.total} heads, ${feedback.relations_correct} of ${feedback.total} relations match the annotation`}
          body="Heads and relations are compared with the treebank's annotation. Universal Dependencies has particular conventions, such as content words heading function words: the noun, not the preposition, heads a prepositional phrase. Check the definitions when you disagree."
        >
          <Button variant="outline" size="sm" className="mt-3" onClick={() => setShowKey((s) => !s)}>
            {showKey ? "Hide the annotated graph" : "Show the annotated graph"}
          </Button>
        </ScoreBanner>
      ) : null}
      {feedback && showKey ? (
        <div className="space-y-2">
          <h2 className="text-sm font-medium">The annotation</h2>
          <Graph exercise={exercise} arcs={keyArcs} label="Annotated dependency graph" glossary={glossary} />
          <ul className="space-y-1 text-xs text-ink-soft">
            {[...new Set(keyArcs.map((a) => a.relation))].map((r) => (
              <li key={r}>
                <span className="font-medium text-ink">{r}</span>
                {relationName(r) ? `: ${relationName(r)}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <AnswerKeyNote exercise={exercise} />
    </div>
  );
}
