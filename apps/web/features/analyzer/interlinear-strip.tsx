"use client";

import type { Glossary, SentenceAnalysis } from "@/lib/api/types";
import { glossFeatures, posFamily } from "@/lib/syntax/glossary";
import { posColor } from "@/lib/theme";
import { cn } from "@/lib/utils";

import type { Highlight, Selection } from "./selection";

interface InterlinearStripProps {
  sentence: SentenceAnalysis;
  highlight: Highlight;
  selection: Selection;
  posGlossary: Glossary | undefined;
  featureGlossary: Glossary | undefined;
  onSelect: (selection: Selection) => void;
}

/**
 * Word-by-word analysis aligned in columns, after the interlinear glossing convention of
 * linguistics. It is also the accessible, text-only view of the analysis.
 */
export function InterlinearStrip({
  sentence,
  highlight,
  selection,
  posGlossary,
  featureGlossary,
  onSelect,
}: InterlinearStripProps) {
  const arcs = new Map((sentence.dependency?.arcs ?? []).map((a) => [a.dependent, a]));
  const formOf = new Map(sentence.tokens.map((t) => [t.id, t.form]));
  const mwtStart = new Map(sentence.multiword_tokens.map((m) => [m.first, m]));
  const insideMwt = new Set(
    sentence.multiword_tokens.flatMap((m) =>
      Array.from({ length: m.last - m.first }, (_, i) => m.first + 1 + i),
    ),
  );

  const rowHeader = "sticky left-0 z-10 bg-sheet pr-4 text-left align-top text-xs font-medium text-graphite";
  const cell = (id: number) =>
    cn(
      "px-2.5 align-top whitespace-nowrap",
      highlight.tokens.has(id) && "bg-highlight-soft",
      selection?.kind === "token" && selection.id === id && "bg-highlight",
    );

  return (
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Word-by-word analysis">
      <table className="border-separate border-spacing-y-1 text-sm">
        <caption className="sr-only">
          Each column is one word of the sentence: its form, lemma, part of speech, grammatical
          features and dependency relation.
        </caption>
        <tbody>
          {sentence.multiword_tokens.length > 0 ? (
            <tr>
              <th scope="row" className={rowHeader}>
                Written as
              </th>
              {sentence.tokens.map((t) => {
                if (insideMwt.has(t.id)) return null;
                const mwt = mwtStart.get(t.id);
                return mwt ? (
                  <td
                    key={t.id}
                    colSpan={mwt.last - mwt.first + 1}
                    className="px-2.5 text-center font-data text-graphite"
                  >
                    <span className="border-b border-rule-strong px-1">{mwt.form}</span>
                  </td>
                ) : (
                  <td key={t.id} />
                );
              })}
            </tr>
          ) : null}
          <tr>
            <th scope="row" className={rowHeader}>
              Word
            </th>
            {sentence.tokens.map((t) => (
              <td key={t.id} className={cn(cell(t.id), "rounded-t")}>
                <button
                  type="button"
                  className="font-data text-[1.0625rem] leading-tight text-ink hover:underline"
                  aria-pressed={selection?.kind === "token" && selection.id === t.id}
                  onClick={() => onSelect({ kind: "token", id: t.id })}
                >
                  {t.form}
                </button>
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row" className={rowHeader}>
              Lemma
            </th>
            {sentence.tokens.map((t) => (
              <td key={t.id} className={cn(cell(t.id), "font-data italic text-ink-soft")}>
                {t.lemma ?? "—"}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row" className={rowHeader}>
              Part of speech
            </th>
            {sentence.tokens.map((t) => (
              <td
                key={t.id}
                className={cn(cell(t.id), "small-caps font-data font-bold")}
                style={{ color: posColor(posFamily(posGlossary, t.upos)) }}
              >
                {t.upos ?? "—"}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row" className={rowHeader}>
              Features
            </th>
            {sentence.tokens.map((t) => {
              const parts = glossFeatures(t.feats, featureGlossary);
              return (
                <td key={t.id} className={cn(cell(t.id), "small-caps font-data text-ink-soft")}>
                  {parts.length ? parts.map((p) => p.gloss).join(".") : ""}
                </td>
              );
            })}
          </tr>
          {sentence.dependency ? (
            <tr>
              <th scope="row" className={rowHeader}>
                Relation
              </th>
              {sentence.tokens.map((t) => {
                const arc = arcs.get(t.id);
                return (
                  <td key={t.id} className={cn(cell(t.id), "rounded-b text-xs text-ink-soft")}>
                    {arc ? (
                      <button
                        type="button"
                        className="text-left hover:underline"
                        onClick={() => onSelect({ kind: "arc", dependent: t.id })}
                      >
                        <span className="font-medium text-ink">{arc.relation}</span>
                        {arc.head > 0 ? (
                          <span className="block font-data text-[0.8125rem] italic">
                            of {formOf.get(arc.head)}
                          </span>
                        ) : null}
                      </button>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
