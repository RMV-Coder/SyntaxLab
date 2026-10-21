"use client";

import { useId, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { LanguageDetail, LanguageSummary, StructureKind } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STRUCTURE_LABELS: Record<StructureKind, { title: string; hint: string }> = {
  constituency: { title: "Phrase structure", hint: "constituency tree" },
  dependency: { title: "Word relations", hint: "dependency graph" },
};

interface SentenceFormProps {
  languages: LanguageSummary[];
  language: string | null;
  detail: LanguageDetail | null;
  text: string;
  structures: StructureKind[];
  busy: boolean;
  onLanguageChange: (code: string) => void;
  onTextChange: (text: string) => void;
  onStructuresChange: (structures: StructureKind[]) => void;
  onSubmit: (text?: string) => void;
  onClear: () => void;
}

export function validateText(text: string, detail: LanguageDetail | null): string | null {
  const trimmed = text.trim();
  if (!trimmed) return "Enter a sentence to analyze.";
  if (detail && trimmed.length > detail.limits.max_chars) {
    return `Keep it under ${detail.limits.max_chars} characters (currently ${trimmed.length}).`;
  }
  if (detail && trimmed.split(/\s+/).length > detail.limits.max_words) {
    return `Keep it under ${detail.limits.max_words} words.`;
  }
  return null;
}

export function SentenceForm({
  languages,
  language,
  detail,
  text,
  structures,
  busy,
  onLanguageChange,
  onTextChange,
  onStructuresChange,
  onSubmit,
  onClear,
}: SentenceFormProps) {
  const ids = { text: useId(), hint: useId(), error: useId(), language: useId() };
  const error = text.trim() ? validateText(text, detail) : null;
  const scheme = (structure: StructureKind) =>
    detail?.capabilities.find((c) => c.capability === structure)?.scheme?.name;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!validateText(text, detail)) onSubmit();
  };

  return (
    <form onSubmit={submit} className="space-y-5" aria-busy={busy}>
      <div className="space-y-1.5">
        <Label htmlFor={ids.language}>Language</Label>
        <Select value={language ?? undefined} onValueChange={onLanguageChange} disabled={!languages.length}>
          <SelectTrigger id={ids.language} className="w-full bg-sheet">
            <SelectValue placeholder="Loading languages…" />
          </SelectTrigger>
          <SelectContent>
            {languages.map((l) => (
              <SelectItem key={l.code} value={l.code}>
                {l.name}
                {l.native_name && l.native_name !== l.name ? ` (${l.native_name})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {detail && detail.status !== "ready" ? (
          <p className="text-xs text-graphite" role="status">
            {detail.status === "failed"
              ? `The ${detail.name} models failed to load on the server.`
              : `The ${detail.name} models are loading on the server. The first analysis may take a minute.`}
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <Label htmlFor={ids.text}>Sentence</Label>
          {detail ? (
            <span
              className={cn(
                "text-xs tabular-nums",
                text.trim().length > detail.limits.max_chars ? "text-destructive" : "text-graphite",
              )}
            >
              {text.trim().length} / {detail.limits.max_chars}
            </span>
          ) : null}
        </div>
        <textarea
          id={ids.text}
          value={text}
          rows={4}
          spellCheck={false}
          lang={detail?.code}
          placeholder="The child is eating rice."
          aria-invalid={Boolean(error)}
          aria-describedby={`${ids.hint}${error ? ` ${ids.error}` : ""}`}
          className="w-full resize-y rounded-md border border-input bg-sheet px-3 py-2.5 font-data text-lg leading-snug text-ink placeholder:text-graphite/70 focus-visible:outline-2 focus-visible:outline-ink"
          onChange={(e) => onTextChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              if (!validateText(text, detail)) onSubmit();
            }
          }}
        />
        <p id={ids.hint} className="text-xs text-graphite">
          One sentence at a time. Press Ctrl+Enter to analyze.
        </p>
        {error ? (
          <p id={ids.error} className="text-xs text-destructive">
            {error}
          </p>
        ) : null}
      </div>

      {detail && detail.structures.length > 0 ? (
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">Show</legend>
          {detail.structures.map((s) => {
            const checked = structures.includes(s);
            return (
              <div key={s} className="flex items-start gap-2.5">
                <Checkbox
                  id={`${ids.text}-${s}`}
                  checked={checked}
                  disabled={checked && structures.length === 1}
                  onCheckedChange={(value) =>
                    onStructuresChange(
                      value ? [...structures, s] : structures.filter((x) => x !== s),
                    )
                  }
                  className="mt-0.5"
                />
                <Label htmlFor={`${ids.text}-${s}`} className="flex-col items-start gap-0 font-normal">
                  <span className="font-medium">{STRUCTURE_LABELS[s]?.title ?? s}</span>
                  <span className="text-xs text-graphite">
                    {STRUCTURE_LABELS[s]?.hint ?? s}
                    {scheme(s) ? `, ${scheme(s)}` : ""}
                  </span>
                </Label>
              </div>
            );
          })}
        </fieldset>
      ) : null}

      <div className="flex gap-2">
        <Button type="submit" disabled={busy || !detail || Boolean(validateText(text, detail))} className="flex-1">
          {busy ? "Analyzing…" : "Analyze"}
        </Button>
        <Button type="button" variant="outline" onClick={onClear} disabled={busy || !text}>
          Clear
        </Button>
      </div>

      {detail?.samples.length ? (
        <div className="space-y-2">
          <h2 className="text-sm font-medium">Examples</h2>
          <ul className="space-y-1.5">
            {detail.samples.map((sample) => (
              <li key={sample.text}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    onTextChange(sample.text);
                    onSubmit(sample.text);
                  }}
                  className="w-full rounded-md px-2 py-1.5 text-left hover:bg-muted disabled:opacity-60"
                >
                  <span className="block font-data text-[0.9375rem] text-ink">{sample.text}</span>
                  {sample.note ? (
                    <span className="mt-0.5 block text-xs leading-snug text-graphite">{sample.note}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </form>
  );
}
