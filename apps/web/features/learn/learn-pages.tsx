"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api/client";
import type { ExerciseDetail, ExerciseKind, ExerciseSummary } from "@/lib/api/types";

import { useGlossaries } from "../analyzer/hooks";
import { DependencyExercise } from "./dependency-exercise";
import { PosExercise } from "./pos-exercise";
import { readProgress, type ProgressMap } from "./progress";
import { TreeExercise } from "./tree-exercise";

const SECTIONS: Record<ExerciseKind, { title: string; intro: string }> = {
  pos: {
    title: "Parts of speech",
    intro:
      "Tag each word of a real sentence. Answers are compared with the expert annotation of the UD English Web Treebank.",
  },
  dependency: {
    title: "Word relations",
    intro:
      "Connect each word to the word it depends on and name the relation, then compare your graph with the treebank's.",
  },
  constituency: {
    title: "Build a tree",
    intro:
      "Bracket a sentence into phrases under a small teaching grammar. Every tree the grammar allows is accepted, so ambiguous sentences have more than one right answer.",
  },
};

const DIFFICULTY = ["", "short", "medium", "longer"];

export function ExerciseListPage() {
  const [exercises, setExercises] = useState<ExerciseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Read once on the client; the list using it only renders after the exercises load.
  const [progress] = useState<ProgressMap>(() => (typeof window === "undefined" ? {} : readProgress()));

  useEffect(() => {
    const controller = new AbortController();
    api
      .exercises(controller.signal)
      .then((r) => setExercises(r.exercises))
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e.message);
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="font-data text-4xl font-bold text-ink">Practice</h1>
      <p className="mt-3 max-w-2xl leading-relaxed text-ink-soft">
        Exercises use expert-annotated sentences and explicit grammars, never a parser&rsquo;s guess,
        as their answer keys. Each exercise says exactly what your answer is compared with.
      </p>
      {error ? (
        <p role="alert" className="mt-6 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {exercises === null && !error ? <p className="mt-6 text-sm text-graphite">Loading exercises…</p> : null}
      {(Object.keys(SECTIONS) as ExerciseKind[]).map((kind) => {
        const items = exercises?.filter((e) => e.kind === kind) ?? [];
        if (!items.length) return null;
        const solved = items.filter((e) => progress[e.id]?.solved).length;
        return (
          <section key={kind} className="mt-10" aria-labelledby={`h-${kind}`}>
            <div className="flex items-baseline justify-between gap-3 border-b border-rule pb-2">
              <h2 id={`h-${kind}`} className="font-data text-2xl font-bold">
                {SECTIONS[kind].title}
              </h2>
              <span className="text-xs text-graphite">
                {solved} of {items.length} solved
              </span>
            </div>
            <p className="mt-2 text-sm text-ink-soft">{SECTIONS[kind].intro}</p>
            <ul className="mt-3 divide-y divide-rule">
              {items.map((e) => (
                <li key={e.id}>
                  <Link href={`/learn/${e.id}`} className="flex items-baseline gap-3 py-2.5 hover:bg-muted">
                    <span className="w-5 shrink-0">
                      {progress[e.id]?.solved ? (
                        <Check aria-label="Solved" className="size-4 text-pos-modifier" />
                      ) : null}
                    </span>
                    <span className="flex-1 font-data text-lg text-ink">{e.title}</span>
                    <span className="text-xs text-graphite">{DIFFICULTY[e.difficulty]}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      <p className="mt-10 text-xs text-graphite">
        Progress is saved in this browser only. Treebank sentences: UD English-EWT (CC BY-SA 4.0).
      </p>
    </div>
  );
}

export function ExercisePage({ id }: { id: string }) {
  const [exercise, setExercise] = useState<ExerciseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const glossaries = useGlossaries(exercise?.kind === "pos" ? ["ud-upos"] : exercise?.kind === "dependency" ? ["ud-2"] : []);

  useEffect(() => {
    const controller = new AbortController();
    api
      .exercise(id, controller.signal)
      .then(setExercise)
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e.message);
      });
    return () => controller.abort();
  }, [id]);

  return (
    <div className="mx-auto max-w-4xl px-5 py-8">
      <Link href="/learn" className="text-sm text-ink-soft underline underline-offset-2">
        All exercises
      </Link>
      {error ? (
        <p role="alert" className="mt-6 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {exercise ? (
        <article className="mt-4 space-y-6">
          <header>
            <p className="text-xs text-graphite">{SECTIONS[exercise.kind].title}</p>
            <h1 className="mt-1 font-data text-3xl text-ink" lang={exercise.language ?? undefined}>
              {exercise.title}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">{exercise.instructions}</p>
          </header>
          {exercise.kind === "pos" ? <PosExercise exercise={exercise} glossary={glossaries["ud-upos"]} /> : null}
          {exercise.kind === "dependency" ? (
            <DependencyExercise exercise={exercise} glossary={glossaries["ud-2"]} />
          ) : null}
          {exercise.kind === "constituency" ? <TreeExercise exercise={exercise} /> : null}
        </article>
      ) : !error ? (
        <p className="mt-6 text-sm text-graphite">Loading…</p>
      ) : null}
    </div>
  );
}
