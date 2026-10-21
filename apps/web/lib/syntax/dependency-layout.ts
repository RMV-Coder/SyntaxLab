import type { DependencyArc, Token } from "@/lib/api/types";

import type { Measure } from "./constituency-layout";

export interface DependencyLayoutOptions {
  levelHeight: number;
  tokenGap: number;
  padding: number;
  cornerRadius: number;
  rootHeight: number;
  /** Horizontal step between arcs leaving the same word, so they stay distinguishable. */
  headOffset: number;
}

const DEFAULTS: DependencyLayoutOptions = {
  levelHeight: 30,
  tokenGap: 26,
  padding: 24,
  cornerRadius: 6,
  rootHeight: 30,
  headOffset: 4,
};

export interface LaidToken {
  id: number;
  x: number;
  width: number;
}

export interface LaidArc {
  dependent: number;
  head: number;
  relation: string;
  level: number;
  /** x of the head end and the dependent end. */
  x1: number;
  x2: number;
  top: number;
  path: string;
  labelX: number;
  labelY: number;
}

export interface DependencyLayout {
  tokens: LaidToken[];
  arcs: LaidArc[];
  root: { tokenId: number; x: number; top: number } | null;
  baseY: number;
  wordY: number;
  tagY: number;
  width: number;
  height: number;
  maxLevel: number;
}

/**
 * Nesting level of each arc: 1 + the highest level of any arc whose span lies within it.
 * Inner arcs are therefore always drawn lower than the arcs enclosing them. Crossing
 * (non-projective) arcs get independent levels and may intersect, which is faithful to the
 * analysis rather than an artefact to hide.
 */
export function arcLevels(arcs: readonly DependencyArc[]): Map<number, number> {
  const spans = arcs
    .filter((a) => a.head !== 0)
    .map((a) => ({
      dependent: a.dependent,
      lo: Math.min(a.head, a.dependent),
      hi: Math.max(a.head, a.dependent),
    }))
    .sort((a, b) => a.hi - a.lo - (b.hi - b.lo));
  const levels = new Map<number, number>();
  for (const [i, s] of spans.entries()) {
    let level = 1;
    for (const inner of spans.slice(0, i)) {
      if (inner.lo >= s.lo && inner.hi <= s.hi) {
        level = Math.max(level, (levels.get(inner.dependent) ?? 0) + 1);
      }
    }
    levels.set(s.dependent, level);
  }
  return levels;
}

export function layoutDependency(
  tokens: readonly Token[],
  arcs: readonly DependencyArc[],
  measure: Measure,
  options: Partial<DependencyLayoutOptions> = {},
): DependencyLayout {
  const opts = { ...DEFAULTS, ...options };
  const levels = arcLevels(arcs);
  const maxLevel = Math.max(0, ...levels.values());

  const baseY = opts.padding + opts.rootHeight + maxLevel * opts.levelHeight;
  const wordY = baseY + 22;
  const tagY = wordY + 22;

  const laidTokens: LaidToken[] = [];
  let cursor = opts.padding;
  for (const t of tokens) {
    const width = Math.max(measure(t.form, "word"), measure(t.upos ?? "", "label"), 18);
    laidTokens.push({ id: t.id, x: cursor + width / 2, width });
    cursor += width + opts.tokenGap;
  }
  const xOf = new Map(laidTokens.map((t) => [t.id, t.x]));
  const r = opts.cornerRadius;

  // Arcs leaving the same head on the same side start at staggered offsets, inner (lower)
  // arcs nearest the word, so they do not merge into one line.
  const startOffset = new Map<number, number>();
  const groups = new Map<string, DependencyArc[]>();
  for (const arc of arcs) {
    if (arc.head === 0) continue;
    const key = `${arc.head}:${Math.sign(arc.dependent - arc.head)}`;
    groups.set(key, [...(groups.get(key) ?? []), arc]);
  }
  for (const group of groups.values()) {
    group
      .sort((a, b) => (levels.get(a.dependent) ?? 0) - (levels.get(b.dependent) ?? 0))
      .forEach((arc, rank) => startOffset.set(arc.dependent, opts.headOffset * (rank + 1)));
  }

  const laidArcs: LaidArc[] = [];
  let root: DependencyLayout["root"] = null;
  for (const arc of arcs) {
    const xd = xOf.get(arc.dependent) ?? 0;
    if (arc.head === 0) {
      root = { tokenId: arc.dependent, x: xd, top: opts.padding };
      continue;
    }
    const level = levels.get(arc.dependent) ?? 1;
    const top = baseY - level * opts.levelHeight;
    const direction = Math.sign(xd - (xOf.get(arc.head) ?? 0)) || 1;
    const x1 = (xOf.get(arc.head) ?? 0) + direction * (startOffset.get(arc.dependent) ?? opts.headOffset);
    const x2 = xd;
    const path = [
      `M ${x1} ${baseY}`,
      `L ${x1} ${top + r}`,
      `Q ${x1} ${top} ${x1 + direction * r} ${top}`,
      `L ${x2 - direction * r} ${top}`,
      `Q ${x2} ${top} ${x2} ${top + r}`,
      `L ${x2} ${baseY}`,
    ].join(" ");
    laidArcs.push({
      dependent: arc.dependent,
      head: arc.head,
      relation: arc.relation,
      level,
      x1,
      x2,
      top,
      path,
      labelX: (x1 + x2) / 2,
      labelY: top,
    });
  }

  return {
    tokens: laidTokens,
    arcs: laidArcs,
    root,
    baseY,
    wordY,
    tagY,
    width: Math.max(cursor - opts.tokenGap + opts.padding, opts.padding * 2),
    height: tagY + opts.padding,
    maxLevel,
  };
}
