/**
 * The tree builder's model: a student builds a phrase-structure tree by bracketing word spans
 * and labelling them. Nesting follows from containment (the same rule the server uses when it
 * checks the answer), so the preview always shows exactly what will be checked.
 *
 * For constituents with identical spans (unary chains such as NP over Pronoun), the one
 * created first dominates; the student can reorder them.
 */
import type { DerivationTree } from "@/lib/api/types";

export interface Constituent {
  id: string;
  label: string;
  /** First word, 0-based. */
  start: number;
  /** One past the last word. */
  end: number;
}

export type AddResult =
  | { ok: true; list: Constituent[] }
  | { ok: false; reason: "crossing" | "duplicate"; conflict: Constituent };

const crosses = (a: Constituent, b: { start: number; end: number }) =>
  (a.start < b.start && b.start < a.end && a.end < b.end) ||
  (b.start < a.start && a.start < b.end && b.end < a.end);

let counter = 0;
export const newId = () => `c${Date.now().toString(36)}${(counter++).toString(36)}`;

export function addConstituent(
  list: Constituent[],
  label: string,
  start: number,
  end: number,
  id = newId(),
): AddResult {
  const duplicate = list.find((c) => c.label === label && c.start === start && c.end === end);
  if (duplicate) return { ok: false, reason: "duplicate", conflict: duplicate };
  const conflict = list.find((c) => crosses(c, { start, end }));
  if (conflict) return { ok: false, reason: "crossing", conflict };
  return { ok: true, list: [...list, { id, label, start, end }] };
}

export function removeConstituent(list: Constituent[], id: string): Constituent[] {
  return list.filter((c) => c.id !== id);
}

export function relabel(list: Constituent[], id: string, label: string): Constituent[] {
  return list.map((c) => (c.id === id ? { ...c, label } : c));
}

/** Constituents covering exactly the same words as `id`, in dominance order. */
export function chainOf(list: Constituent[], id: string): Constituent[] {
  const target = list.find((c) => c.id === id);
  return target ? list.filter((c) => c.start === target.start && c.end === target.end) : [];
}

/** Move a constituent up (towards the top) or down within its unary chain. */
export function moveInChain(list: Constituent[], id: string, direction: "up" | "down"): Constituent[] {
  const chain = chainOf(list, id);
  const position = chain.findIndex((c) => c.id === id);
  const swapWith = chain[direction === "up" ? position - 1 : position + 1];
  if (!swapWith) return list;
  const a = list.findIndex((c) => c.id === id);
  const b = list.findIndex((c) => c.id === swapWith.id);
  const next = [...list];
  [next[a], next[b]] = [next[b], next[a]];
  return next;
}

export interface BuiltNode {
  constituent: Constituent;
  children: BuiltNode[];
  depth: number;
}

/** Nest constituents by containment; returns top-level nodes in sentence order. */
export function nest(list: Constituent[]): BuiltNode[] {
  const order = list
    .map((c, index) => ({ c, index }))
    .sort((x, y) => x.c.start - y.c.start || y.c.end - x.c.end || x.index - y.index);
  const roots: BuiltNode[] = [];
  const stack: BuiltNode[] = [];
  for (const { c } of order) {
    while (stack.length && !(stack[stack.length - 1].constituent.start <= c.start && c.end <= stack[stack.length - 1].constituent.end)) {
      stack.pop();
    }
    const node: BuiltNode = { constituent: c, children: [], depth: stack.length };
    (stack.length ? stack[stack.length - 1].children : roots).push(node);
    stack.push(node);
  }
  return roots;
}

/** Flattened outline (pre-order) for listing constituents with indentation. */
export function outline(list: Constituent[]): BuiltNode[] {
  const out: BuiltNode[] = [];
  const visit = (n: BuiltNode) => {
    out.push(n);
    n.children.forEach(visit);
  };
  nest(list).forEach(visit);
  return out;
}

export const PLACEHOLDER_ROOT = "…";

/**
 * A derivation tree for the live preview. Words not inside any constituent hang directly
 * under their nearest constituent; if there is no single constituent over the whole sentence,
 * a placeholder root (…) holds the pieces built so far.
 */
export function previewTree(list: Constituent[], words: string[]): DerivationTree {
  const toTree = (node: BuiltNode): DerivationTree => {
    const { start, end, label } = node.constituent;
    return {
      symbol: label,
      kind: "nonterminal",
      start,
      end,
      rule: null,
      token: null,
      children: fill(node.children.map(toTree), start, end),
    };
  };
  const fill = (children: DerivationTree[], start: number, end: number): DerivationTree[] => {
    const covered = new Set(children.flatMap((c) => range(c.start, c.end)));
    const leaves: DerivationTree[] = range(start, end)
      .filter((i) => !covered.has(i))
      .map((i) => ({ symbol: words[i], kind: "terminal", start: i, end: i + 1, rule: null, token: i, children: [] }));
    return [...children, ...leaves].sort((a, b) => a.start - b.start);
  };
  const roots = nest(list).map(toTree);
  const n = words.length;
  if (roots.length === 1 && roots[0].start === 0 && roots[0].end === n) return roots[0];
  return {
    symbol: PLACEHOLDER_ROOT,
    kind: "nonterminal",
    start: 0,
    end: n,
    rule: null,
    token: null,
    children: fill(roots, 0, n),
  };
}

export function isComplete(list: Constituent[], wordCount: number): boolean {
  return list.some((c) => c.start === 0 && c.end === wordCount);
}

function range(start: number, end: number): number[] {
  return Array.from({ length: Math.max(0, end - start) }, (_, i) => start + i);
}
