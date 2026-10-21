import type { DerivationTree } from "@/lib/api/types";

import type { Measure } from "./constituency-layout";

/**
 * Layout for derivation trees produced by the Algorithm Lab's Earley parser.
 *
 * Unlike treebank trees, a grammar may put words directly inside any rule (VP → "to" V) and
 * may derive the empty string (Det → ε), so leaves are either words or ε. Words sit on one
 * baseline in sentence order; a node whose children are all leaves sits on the row just above
 * them (like a pre-terminal); other nodes are placed by depth, centred over their children.
 */

export interface DerivationNodeLayout {
  /** Path from the root, e.g. "0.1.0"; stable identifier within one tree. */
  id: string;
  label: string;
  kind: "nonterminal" | "word" | "empty";
  x: number;
  y: number;
  start: number;
  end: number;
  rule: number | null;
  parentId: string | null;
  tree: DerivationTree | null;
}

export interface DerivationLayout {
  nodes: DerivationNodeLayout[];
  edges: { from: string; to: string }[];
  width: number;
  height: number;
  wordY: number;
}

const LEVEL = 56;
const GAP = 22;
const PAD = 28;

export function layoutDerivation(tree: DerivationTree, measure: Measure): DerivationLayout {
  interface Draft {
    id: string;
    tree: DerivationTree | null; // null for synthetic ε leaves
    depth: number;
    children: Draft[];
    parentId: string | null;
  }

  const build = (t: DerivationTree, id: string, depth: number, parentId: string | null): Draft => {
    const children =
      t.kind === "nonterminal" && t.children.length === 0
        ? [{ id: `${id}.ε`, tree: null, depth: depth + 1, children: [], parentId: id }]
        : t.children.map((c, i) => build(c, `${id}.${i}`, depth + 1, id));
    return { id, tree: t, depth, children, parentId };
  };
  const root = build(tree, "0", 0, null);

  const leaves: Draft[] = [];
  let maxDepth = 0;
  const walk = (d: Draft) => {
    maxDepth = Math.max(maxDepth, d.depth);
    if (d.children.length === 0) leaves.push(d);
    d.children.forEach(walk);
  };
  walk(root);

  // Pre-terminal-like nodes (all children are leaves) sit on the row above the words.
  const preterminalRow = PAD + (maxDepth - 1) * LEVEL;
  const wordY = PAD + maxDepth * LEVEL;

  const xOf = new Map<string, number>();
  let cursor = PAD;
  for (const leaf of leaves) {
    const text = leaf.tree ? leaf.tree.symbol : "ε";
    const width = Math.max(measure(text, "word"), 14);
    xOf.set(leaf.id, cursor + width / 2);
    cursor += width + GAP;
  }

  const nodes: DerivationNodeLayout[] = [];
  const edges: { from: string; to: string }[] = [];
  const place = (d: Draft): number => {
    let x: number;
    if (d.children.length === 0) {
      x = xOf.get(d.id) ?? 0;
    } else {
      const xs = d.children.map(place);
      x = (xs[0] + xs[xs.length - 1]) / 2;
      for (const c of d.children) edges.push({ from: d.id, to: c.id });
    }
    const isLeaf = d.children.length === 0;
    const allLeaves = !isLeaf && d.children.every((c) => c.children.length === 0);
    const t = d.tree;
    nodes.push({
      id: d.id,
      label: t ? t.symbol : "ε",
      kind: !t ? "empty" : t.kind === "terminal" ? "word" : "nonterminal",
      x,
      y: isLeaf ? wordY : allLeaves ? preterminalRow : PAD + d.depth * LEVEL,
      start: t ? t.start : -1,
      end: t ? t.end : -1,
      rule: t ? t.rule : null,
      parentId: d.parentId,
      tree: t,
    });
    return x;
  };
  place(root);

  return {
    nodes,
    edges,
    width: Math.max(cursor - GAP + PAD, PAD * 2),
    height: wordY + PAD,
    wordY,
  };
}

/** Labelled bracketing of a derivation tree, e.g. [S [NP [Pronoun I]] …]; ε for empty nodes. */
export function derivationBrackets(tree: DerivationTree): string {
  if (tree.kind === "terminal") return tree.symbol;
  if (tree.children.length === 0) return `[${tree.symbol} ε]`;
  return `[${tree.symbol} ${tree.children.map(derivationBrackets).join(" ")}]`;
}
