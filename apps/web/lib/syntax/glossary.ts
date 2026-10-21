import type { Glossary, GlossaryEntry } from "@/lib/api/types";

export type LookupMatch = "exact" | "base" | "none";

export interface LabelLookup {
  entry: GlossaryEntry | null;
  match: LookupMatch;
  /** For subtype fallbacks ("nsubj:outer" -> "nsubj"), the label that matched. */
  matchedLabel: string | null;
}

/**
 * Finds the curated explanation of a label. UD relation subtypes without their own entry fall
 * back to the base relation, and the caller is told so (match = "base") so the UI can say that
 * only the general relation is described.
 */
export function lookupLabel(glossary: Glossary | null | undefined, label: string): LabelLookup {
  if (!glossary) return { entry: null, match: "none", matchedLabel: null };
  const exact = glossary.entries[label];
  if (exact) return { entry: exact, match: "exact", matchedLabel: label };
  const base = label.split(":")[0];
  if (base !== label && glossary.entries[base]) {
    return { entry: glossary.entries[base], match: "base", matchedLabel: base };
  }
  return { entry: null, match: "none", matchedLabel: null };
}

/** Conventional order of grammatical categories in an interlinear gloss. */
const GLOSS_ORDER = [
  "Person",
  "Number",
  "Gender",
  "Case",
  "Definite",
  "PronType",
  "Poss",
  "Reflex",
  "Tense",
  "Aspect",
  "Mood",
  "Voice",
  "VerbForm",
  "Polarity",
  "Degree",
];

export interface GlossPart {
  feature: string;
  value: string;
  gloss: string;
  standard: boolean;
}

/**
 * Leipzig-style gloss abbreviations for a word's morphological features, e.g.
 * {Person: 3, Number: Sing, Tense: Pres} -> 3, SG, PRS. Features without a curated gloss are
 * omitted here (they remain visible in full in the inspector).
 */
export function glossFeatures(
  feats: Record<string, string>,
  glossary: Glossary | null | undefined,
): GlossPart[] {
  if (!glossary) return [];
  const rank = (f: string) => {
    const i = GLOSS_ORDER.indexOf(f);
    return i === -1 ? GLOSS_ORDER.length : i;
  };
  return Object.entries(feats)
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .flatMap(([feature, raw]) =>
      // UD allows multiple values separated by commas (e.g. PronType=Int,Rel).
      raw.split(",").flatMap((value) => {
        const v = glossary.entries[feature]?.values?.[value];
        return v?.gloss
          ? [{ feature, value, gloss: v.gloss, standard: v.gloss_standard ?? true }]
          : [];
      }),
    );
}

export function posFamily(glossary: Glossary | null | undefined, upos: string | null | undefined) {
  if (!upos || !glossary) return null;
  return glossary.entries[upos]?.family ?? null;
}
