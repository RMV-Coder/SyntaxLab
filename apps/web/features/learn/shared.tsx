"use client";

import { Check, CircleDashed, X } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { ExerciseDetail } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export const selectClass =
  "w-full rounded-md border border-input bg-sheet px-2 py-1.5 text-sm text-ink disabled:opacity-60";

export function AnswerKeyNote({ exercise }: { exercise: ExerciseDetail }) {
  const key = exercise.answer_key;
  return (
    <p className="text-xs leading-relaxed text-graphite">
      <span className="font-medium text-ink-soft">How answers are checked. </span>
      {key.description}
      {key.treebank ? (
        <>
          {" "}
          Source: {key.treebank} {key.release}, sentence {key.sent_id} ({key.license}).
        </>
      ) : null}
    </p>
  );
}

export type Mark = "correct" | "incorrect" | "partial" | "unanswered";

export function MarkIcon({ mark, className }: { mark: Mark; className?: string }) {
  const label = { correct: "Correct", incorrect: "Incorrect", partial: "Partly correct", unanswered: "Not answered" }[mark];
  const Icon = mark === "correct" ? Check : mark === "unanswered" ? CircleDashed : X;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        mark === "correct" && "text-pos-modifier",
        mark === "incorrect" && "text-destructive",
        mark === "partial" && "text-pos-function",
        mark === "unanswered" && "text-graphite",
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {label}
    </span>
  );
}

export function ScoreBanner({
  title,
  body,
  solved,
  children,
}: {
  title: string;
  body: string;
  solved: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      role="status"
      className={cn(
        "rounded-md border-l-4 bg-sheet p-4",
        solved ? "border-pos-modifier" : "border-pos-function",
      )}
    >
      <p className="font-data text-xl font-bold text-ink">{title}</p>
      <p className="mt-1 text-sm leading-relaxed text-ink-soft">{body}</p>
      {children}
    </div>
  );
}

export function CheckBar({
  busy,
  disabled,
  checked,
  onCheck,
  onReset,
  hint,
}: {
  busy: boolean;
  disabled: boolean;
  checked: boolean;
  onCheck: () => void;
  onReset: () => void;
  hint?: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button onClick={onCheck} disabled={busy || disabled}>
        {busy ? "Checking…" : checked ? "Check again" : "Check my answer"}
      </Button>
      <Button variant="outline" onClick={onReset} disabled={busy}>
        Start over
      </Button>
      {hint ? <span className="text-xs text-graphite">{hint}</span> : null}
    </div>
  );
}
