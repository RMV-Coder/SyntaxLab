"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, API_BASE_URL, ApiError } from "@/lib/api/client";
import type { ParseResponse, StructureKind } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { DiagramPanel } from "./diagram-panel";
import { useGlossaries, useLanguages } from "./hooks";
import { Inspector, type Glossaries } from "./inspector";
import { highlightFor, type Selection } from "./selection";
import { SentenceForm } from "./sentence-form";

type Panel = "input" | "diagram" | "details";
const RETRYABLE = new Set(["network_error", "unexpected_response", "overloaded", "analysis_timeout", "model_unavailable", "rate_limited"]);

function ErrorMessage({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
      <p className="text-ink">{error.message}</p>
      {error.code === "network_error" ? (
        <p className="mt-1 text-xs text-graphite">Expected at {API_BASE_URL}.</p>
      ) : null}
      {onRetry && RETRYABLE.has(error.code) ? (
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mx-auto flex h-full max-w-xl flex-col justify-center px-6 py-12">
      <p className="font-data text-3xl leading-snug text-ink">
        Type a sentence, or start from an example.
      </p>
      <p className="mt-4 leading-relaxed text-ink-soft">
        SyntaxLab draws two complementary analyses. A <em>phrase-structure tree</em> groups words
        into nested constituents such as noun and verb phrases. A <em>dependency graph</em> links
        every word to the word it depends on and names the relation.
      </p>
      <p className="mt-3 leading-relaxed text-ink-soft">
        Both come from trained parsers, not from rules written for your sentence, so they can be
        wrong; the panel on the right always says which model produced what.
      </p>
    </div>
  );
}

export function AnalyzerWorkspace() {
  const [requestedLanguage, setLanguage] = useState<string | null>(null);
  const {
    languages,
    selected: language,
    detail,
    error: languagesError,
    retry,
  } = useLanguages(requestedLanguage);
  const [text, setText] = useState("");
  // Structures the user chose, remembered per language; default: everything supported.
  const [chosen, setChosen] = useState<{ language: string; structures: StructureKind[] } | null>(
    null,
  );
  const structures = useMemo(
    () =>
      chosen && chosen.language === detail?.code ? chosen.structures : (detail?.structures ?? []),
    [chosen, detail],
  );
  const setStructures = (next: StructureKind[]) => {
    if (detail) setChosen({ language: detail.code, structures: next });
  };
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [selection, setSelection] = useState<Selection>(null);
  const [view, setView] = useState<StructureKind>("constituency");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [panel, setPanel] = useState<Panel>("input");
  const request = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(timer);
  }, [busy]);

  const submit = useCallback(
    (override?: string) => {
      if (!language) return;
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      setElapsed(0);
      setError(null);
      api
        .parse({ language, text: override ?? text, structures }, controller.signal)
        .then((response) => {
          setResult(response);
          setSelection(null);
          setCollapsed(new Set());
          const available = (["constituency", "dependency"] as const).filter(
            (s) => response.sentences[0]?.[s],
          );
          setView((current) => (available.includes(current) ? current : (available[0] ?? current)));
          setPanel("diagram");
        })
        .catch((e: unknown) => {
          if (e instanceof ApiError) setError(e);
        })
        .finally(() => {
          if (request.current === controller) setBusy(false);
        });
    },
    [language, text, structures],
  );

  const capabilityScheme = (capability: string) =>
    detail?.capabilities.find((c) => c.capability === capability)?.scheme?.id;
  const schemeIds = {
    pos: capabilityScheme("pos"),
    features: capabilityScheme("morphology"),
    dependency: capabilityScheme("dependency"),
    constituency: capabilityScheme("constituency"),
  };
  const loaded = useGlossaries(Object.values(schemeIds));
  const glossaries: Glossaries = {
    pos: schemeIds.pos ? loaded[schemeIds.pos] : undefined,
    features: schemeIds.features ? loaded[schemeIds.features] : undefined,
    dependency: schemeIds.dependency ? loaded[schemeIds.dependency] : undefined,
    constituency: schemeIds.constituency ? loaded[schemeIds.constituency] : undefined,
  };

  const sentence = result?.sentences[0] ?? null;
  const views = (["constituency", "dependency"] as const).filter((s) => sentence?.[s]);
  const highlight = useMemo(
    () => (sentence ? highlightFor(sentence, selection) : null),
    [sentence, selection],
  );

  const select = (next: Selection) => setSelection(next);
  const toggle = (id: string) =>
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const tabs: { id: Panel; label: string }[] = [
    { id: "input", label: "Sentence" },
    { id: "diagram", label: "Diagram" },
    { id: "details", label: "Details" },
  ];

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <nav aria-label="Workspace panels" className="flex border-b border-rule bg-sheet lg:hidden">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-pressed={panel === t.id}
            onClick={() => setPanel(t.id)}
            className={cn(
              "flex-1 border-b-2 px-3 py-2.5 text-sm font-medium",
              panel === t.id ? "border-ink text-ink" : "border-transparent text-graphite",
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] lg:grid-cols-[21rem_minmax(0,1fr)_23rem]">
        <aside
          aria-label="Sentence input"
          className={cn(
            "min-h-0 overflow-y-auto border-rule bg-paper p-5 lg:block lg:border-r",
            panel !== "input" && "hidden",
          )}
        >
          {languagesError && !languages.length ? (
            <ErrorMessage error={languagesError} onRetry={retry} />
          ) : (
            <SentenceForm
              languages={languages}
              language={language}
              detail={detail}
              text={text}
              structures={structures}
              busy={busy}
              onLanguageChange={(code) => {
                setLanguage(code);
                setResult(null);
                setSelection(null);
              }}
              onTextChange={setText}
              onStructuresChange={setStructures}
              onSubmit={submit}
              onClear={() => {
                setText("");
                setResult(null);
                setSelection(null);
                setError(null);
              }}
            />
          )}
        </aside>

        <section
          aria-label="Diagram"
          aria-busy={busy}
          className={cn("relative min-h-0 min-w-0 flex-col lg:flex", panel === "diagram" ? "flex" : "hidden")}
        >
          {error ? (
            <div className="border-b border-rule p-3">
              <ErrorMessage error={error} onRetry={() => submit()} />
            </div>
          ) : null}
          {sentence && views.length && result ? (
            <DiagramPanel
              language={result.language.code}
              sentence={sentence}
              view={views.includes(view) ? view : views[0]}
              views={[...views]}
              onViewChange={setView}
              highlight={highlight!}
              selection={selection}
              glossaries={glossaries}
              collapsed={collapsed}
              onSelect={select}
              onToggle={toggle}
              onExpandAll={() => setCollapsed(new Set())}
            />
          ) : (
            <EmptyState />
          )}
          {busy ? (
            <div
              role="status"
              className="absolute inset-0 z-20 flex items-center justify-center bg-paper/80"
            >
              <div className="rounded-md border border-rule bg-sheet px-5 py-4 text-center shadow-sm">
                <p className="font-medium text-ink">Analyzing… {elapsed > 0 ? `${elapsed} s` : ""}</p>
                <p className="mt-1 max-w-64 text-xs text-graphite">
                  The parser runs on a CPU, so a sentence usually takes a few seconds.
                </p>
              </div>
            </div>
          ) : null}
        </section>

        <aside
          aria-label="Details"
          // Focusable so keyboard users can scroll it even when it holds only text.
          tabIndex={0}
          className={cn(
            "min-h-0 overflow-y-auto border-rule bg-sheet p-5 lg:block lg:border-l",
            panel !== "details" && "hidden",
          )}
        >
          <Inspector
            result={result}
            sentence={sentence}
            selection={selection}
            glossaries={glossaries}
            language={detail}
            collapsed={collapsed}
            onSelect={(s) => {
              select(s);
            }}
            onToggle={toggle}
          />
        </aside>
      </div>
    </div>
  );
}
