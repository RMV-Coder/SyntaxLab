"use client";

import { useEffect, useRef } from "react";

import type { ParseGrammarResponse, TraceEvent } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { chartAtStep, dottedRule, sameRef } from "./replay";

interface ChartViewProps {
  response: ParseGrammarResponse;
  step: number;
  event: TraceEvent | null;
}

/**
 * The Earley chart at the current step: one column per position, items in the order they
 * were added. The item added by the current step is highlighted; the item that caused it is
 * outlined; for a completion, the finished constituent is underlined.
 */
export function ChartView({ response, step, event }: ChartViewProps) {
  const chart = chartAtStep(response, step);
  const currentRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    currentRef.current?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: reduced ? "auto" : "smooth",
    });
  }, [step]);

  return (
    <div className="overflow-x-auto" role="region" aria-label="Earley chart" tabIndex={0}>
      <ol className="flex min-w-max gap-0">
        {chart.map((column, set) => {
          const isCurrentSet = event?.set === set;
          return (
            <li
              key={set}
              className={cn(
                "w-60 shrink-0 border-r border-rule px-3 py-2 last:border-r-0",
                isCurrentSet && "bg-paper",
              )}
              aria-label={`Set ${set}: ${column.length} item${column.length === 1 ? "" : "s"}`}
            >
              <div className="mb-2 flex items-baseline justify-between gap-2 border-b border-rule pb-1.5">
                <span className="text-xs font-semibold text-ink">Set {set}</span>
                <span className="truncate font-data text-sm text-ink-soft">
                  {set < response.tokens.length ? (
                    <>
                      next word <span className="text-ink">“{response.tokens[set]}”</span>
                    </>
                  ) : (
                    "end of sentence"
                  )}
                </span>
              </div>
              <ol className="space-y-1">
                {column.map((view) => {
                  const added = event?.added && sameRef(event.item, view.ref);
                  const cause = sameRef(event?.cause, view.ref);
                  const completed = sameRef(event?.completed, view.ref);
                  const deadEnd = event?.kind === "scan_fail" && cause;
                  const current = added || (!event?.added && sameRef(event?.item, view.ref));
                  return (
                    <li
                      key={view.ref.index}
                      ref={current || (deadEnd && !current) ? currentRef : undefined}
                      aria-current={current ? "step" : undefined}
                      className={cn(
                        "rounded-sm px-1.5 py-1 font-data text-[0.9375rem] leading-snug",
                        view.complete ? "font-bold text-ink" : "text-ink-soft",
                        current && "bg-highlight text-ink",
                        cause && "outline-1 outline-ink outline-dashed",
                        deadEnd && "bg-destructive/10 line-through decoration-destructive",
                        completed && "underline decoration-2 underline-offset-4",
                      )}
                    >
                      {dottedRule(view.rule, view.item.dot)}
                      <span
                        className={cn(
                          "ml-1.5 align-middle font-sans text-[0.6875rem] font-normal no-underline",
                          current ? "text-ink" : "text-graphite",
                        )}
                      >
                        from {view.item.origin}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
