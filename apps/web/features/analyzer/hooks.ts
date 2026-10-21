"use client";

import { useEffect, useMemo, useState } from "react";

import { api, ApiError } from "@/lib/api/client";
import type { Glossary, LanguageDetail, LanguageSummary } from "@/lib/api/types";
import type { Measure } from "@/lib/syntax/constituency-layout";
import { theme } from "@/lib/theme";

// ------------------------------------------------------------------ languages

export interface LanguagesState {
  languages: LanguageSummary[];
  /** The requested language, or by default the first ready one. */
  selected: string | null;
  detail: LanguageDetail | null;
  error: ApiError | null;
}

/** Discovers languages from the API (nothing about languages is hard-coded in the client). */
export function useLanguages(requested: string | null): LanguagesState & { retry: () => void } {
  const [languages, setLanguages] = useState<LanguageSummary[]>([]);
  const [detail, setDetail] = useState<LanguageDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);

  const selected =
    requested ?? (languages.find((l) => l.status === "ready") ?? languages[0])?.code ?? null;

  useEffect(() => {
    const controller = new AbortController();
    api
      .languages(controller.signal)
      .then((list) => {
        setLanguages(list.languages);
        setError(null);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e);
      });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () =>
      api
        .language(selected, controller.signal)
        .then((d) => {
          setDetail(d);
          // While models load, poll so the UI can say when the language becomes ready.
          if (d.status === "loading" || d.status === "not_loaded") timer = setTimeout(load, 3000);
        })
        .catch((e: unknown) => {
          if (e instanceof ApiError) setError(e);
        });
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [selected, attempt]);

  return {
    languages,
    selected,
    detail: detail?.code === selected ? detail : null,
    error,
    retry: () => setAttempt((a) => a + 1),
  };
}

// ------------------------------------------------------------------ glossaries

const glossaryCache = new Map<string, Promise<Glossary | null>>();

function fetchGlossary(schemeId: string): Promise<Glossary | null> {
  let pending = glossaryCache.get(schemeId);
  if (!pending) {
    // A missing glossary is not an error for the analysis: the UI says no definition exists.
    pending = api.glossary(schemeId).catch(() => {
      glossaryCache.delete(schemeId);
      return null;
    });
    glossaryCache.set(schemeId, pending);
  }
  return pending;
}

/** Glossaries for a set of annotation schemes, keyed by scheme id. */
export function useGlossaries(schemeIds: readonly (string | null | undefined)[]) {
  const key = [...new Set(schemeIds.filter((s): s is string => Boolean(s)))].sort().join("|");
  const [glossaries, setGlossaries] = useState<Record<string, Glossary>>({});
  useEffect(() => {
    let cancelled = false;
    const ids = key ? key.split("|") : [];
    void Promise.all(ids.map(async (id) => [id, await fetchGlossary(id)] as const)).then(
      (entries) => {
        if (cancelled) return;
        setGlossaries(
          Object.fromEntries(entries.filter((e): e is [string, Glossary] => e[1] !== null)),
        );
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key]);
  return glossaries;
}

// ------------------------------------------------------------------ fonts & measuring

export interface DiagramFonts {
  data: string;
  ui: string;
}

/**
 * Resolves the next/font families (whose names are generated at build time) into literal
 * font stacks for SVG text, so the same names can be embedded when a diagram is exported.
 */
export function useDiagramFonts(): { fonts: DiagramFonts; ready: boolean } {
  const [state, setState] = useState<{ fonts: DiagramFonts; ready: boolean }>({
    fonts: { data: theme.fontData, ui: theme.fontUi },
    ready: false,
  });
  useEffect(() => {
    const css = getComputedStyle(document.documentElement);
    const data = css.getPropertyValue("--font-data-face").trim();
    const ui = css.getPropertyValue("--font-ui").trim();
    const fonts = {
      data: data ? `${data}, ${theme.fontData}` : theme.fontData,
      ui: ui ? `${ui}, ${theme.fontUi}` : theme.fontUi,
    };
    const done = () => setState({ fonts, ready: true });
    if (document.fonts?.ready) void document.fonts.ready.then(done);
    else done();
  }, []);
  return state;
}

export const DIAGRAM_TYPE = {
  phraseLabel: { size: 16, weight: 700 },
  tagLabel: { size: 14, weight: 700 },
  word: { size: 17, weight: 400 },
  relation: { size: 12, weight: 500 },
} as const;

let measuringContext: CanvasRenderingContext2D | null | undefined;

function getMeasuringContext(): CanvasRenderingContext2D | null {
  if (measuringContext === undefined) {
    measuringContext =
      typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
  }
  return measuringContext;
}

/** Text width measurement for layout; falls back to an estimate where canvas is unavailable. */
export function useMeasure(fonts: DiagramFonts, ready: boolean): Measure {
  return useMemo(() => {
    // `ready` is part of the identity so layouts recompute once web fonts have loaded.
    const version = ready ? "loaded" : "fallback";
    const measure: Measure = (text, kind) => {
      const spec = kind === "word" ? DIAGRAM_TYPE.word : DIAGRAM_TYPE.phraseLabel;
      const context = getMeasuringContext();
      if (!context) return text.length * spec.size * 0.6;
      // Small capitals render roughly at x-height; measure caps at a reduced size.
      context.font =
        kind === "word"
          ? `${spec.weight} ${spec.size}px ${fonts.data}`
          : `${spec.weight} ${Math.round(spec.size * 0.82)}px ${fonts.data}`;
      return context.measureText(text).width;
    };
    return Object.assign(measure, { version });
  }, [fonts, ready]);
}
