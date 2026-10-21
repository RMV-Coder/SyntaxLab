"use client";

import { useState } from "react";

import { api, ApiError } from "@/lib/api/client";
import type { ExerciseDetail, Glossary, PosFeedback } from "@/lib/api/types";
import { posFamily } from "@/lib/syntax/glossary";
import { posColor } from "@/lib/theme";
import { cn } from "@/lib/utils";

import { recordProgress } from "./progress";
import { AnswerKeyNote, CheckBar, MarkIcon, ScoreBanner, selectClass } from "./shared";

export function PosExercise({ exercise, glossary }: { exercise: ExerciseDetail; glossary?: Glossary }) {
  const empty = () => exercise.tokens.map(() => "");
  const [tags, setTags] = useState<string[]>(empty);
  const [feedback, setFeedback] = useState<PosFeedback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const answered = tags.filter(Boolean).length;

  const check = () => {
    setBusy(true);
    setError(null);
    api
      .checkAnswer(exercise.id, { answer: { kind: "pos", tags: tags.map((t) => t || null) } })
      .then((r) => {
        if (r.feedback.kind !== "pos") return;
        setFeedback(r.feedback);
        recordProgress(exercise.id, r.feedback.correct / r.feedback.total, r.feedback.correct === r.feedback.total);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Checking failed."))
      .finally(() => setBusy(false));
  };

  return (
    <div className="space-y-6">
      <ol className="flex flex-wrap gap-x-3 gap-y-4" aria-label="Words">
        {exercise.tokens.map((token, i) => {
          const item = feedback?.items[i];
          const expected = item?.expected;
          return (
            <li key={token.id} className="w-40">
              <label className="block">
                <span className="block font-data text-xl text-ink">{token.form}</span>
                <select
                  className={cn(selectClass, "mt-1")}
                  value={tags[i]}
                  aria-label={`Part of speech of word ${i + 1}, “${token.form}”`}
                  onChange={(e) => {
                    const next = [...tags];
                    next[i] = e.target.value;
                    setTags(next);
                    setFeedback(null);
                  }}
                >
                  <option value="">Choose…</option>
                  {exercise.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.value}
                      {o.name ? ` (${o.name})` : ""}
                    </option>
                  ))}
                </select>
              </label>
              {item ? (
                <div className="mt-1.5 space-y-1">
                  <MarkIcon mark={item.status} />
                  {item.status !== "correct" ? (
                    <p className="text-xs leading-snug text-ink-soft">
                      The annotation has{" "}
                      <span
                        className="small-caps font-data font-bold"
                        style={{ color: posColor(posFamily(glossary, expected)) }}
                      >
                        {expected}
                      </span>
                      {glossary?.entries[expected ?? ""] ? ` (${glossary.entries[expected ?? ""].name})` : ""}.
                    </p>
                  ) : null}
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>

      <CheckBar
        busy={busy}
        disabled={answered === 0}
        checked={feedback != null}
        onCheck={check}
        onReset={() => {
          setTags(empty());
          setFeedback(null);
        }}
        hint={`${answered} of ${tags.length} words tagged`}
      />
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {feedback ? (
        <ScoreBanner
          solved={feedback.correct === feedback.total}
          title={feedback.correct === feedback.total ? "All tags match the annotation" : `${feedback.correct} of ${feedback.total} match the annotation`}
          body={
            feedback.correct === feedback.total
              ? "Every word has the tag the treebank annotators chose."
              : "Where yours differ, the annotation’s tag is shown under the word. UD has specific conventions (for example, “be” and “have” are AUX when they help another verb), so read the definition before deciding you were wrong."
          }
        >
          {feedback.items.some((i) => i.status === "incorrect") && glossary ? (
            <ul className="mt-3 space-y-2 text-sm">
              {[...new Set(feedback.items.filter((i) => i.status === "incorrect").map((i) => i.expected))].map((tag) => (
                <li key={tag}>
                  <span className="small-caps font-data font-bold" style={{ color: posColor(posFamily(glossary, tag)) }}>
                    {tag}
                  </span>{" "}
                  <span className="text-ink-soft">{glossary.entries[tag]?.definition}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </ScoreBanner>
      ) : null}

      <AnswerKeyNote exercise={exercise} />
    </div>
  );
}
