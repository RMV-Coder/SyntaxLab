import type { SentenceAnalysis } from "@/lib/api/types";

/** What the user has selected; shared by every view so they highlight consistently. */
export type Selection =
  | { kind: "token"; id: number }
  | { kind: "node"; id: string }
  | { kind: "arc"; dependent: number }
  | null;

export interface Highlight {
  /** Words to mark with the highlighter. */
  tokens: Set<number>;
  /** Constituency nodes to emphasize (selected node or path to a selected word). */
  nodes: Set<string>;
  /** Dependency arcs (by dependent id) to emphasize. */
  arcs: Set<number>;
}

const EMPTY: Highlight = { tokens: new Set(), nodes: new Set(), arcs: new Set() };

function parentMap(sentence: SentenceAnalysis): Map<string, string> {
  const parents = new Map<string, string>();
  for (const node of sentence.constituency?.nodes ?? []) {
    for (const child of node.children) parents.set(child, node.id);
  }
  return parents;
}

/** Path from the root to the pre-terminal of `tokenId` (empty without a constituency tree). */
export function pathToToken(sentence: SentenceAnalysis, tokenId: number): string[] {
  const tree = sentence.constituency;
  if (!tree) return [];
  const leaf = tree.nodes.find((n) => n.token_id === tokenId);
  if (!leaf) return [];
  const parents = parentMap(sentence);
  const path = [leaf.id];
  let current = parents.get(leaf.id);
  while (current) {
    path.unshift(current);
    current = parents.get(current);
  }
  return path;
}

export function highlightFor(sentence: SentenceAnalysis, selection: Selection): Highlight {
  if (!selection) return EMPTY;
  const arcs = sentence.dependency?.arcs ?? [];
  switch (selection.kind) {
    case "token": {
      return {
        tokens: new Set([selection.id]),
        nodes: new Set(pathToToken(sentence, selection.id)),
        arcs: new Set(
          arcs
            .filter((a) => a.dependent === selection.id || a.head === selection.id)
            .map((a) => a.dependent),
        ),
      };
    }
    case "node": {
      const node = sentence.constituency?.nodes.find((n) => n.id === selection.id);
      if (!node) return EMPTY;
      const [first, last] = node.span;
      const tokens = new Set<number>();
      for (let i = first; i <= last; i++) tokens.add(i);
      return { tokens, nodes: new Set([node.id]), arcs: new Set() };
    }
    case "arc": {
      const arc = arcs.find((a) => a.dependent === selection.dependent);
      if (!arc) return EMPTY;
      const tokens = new Set([arc.dependent]);
      if (arc.head !== 0) tokens.add(arc.head);
      return { tokens, nodes: new Set(), arcs: new Set([arc.dependent]) };
    }
  }
}

export function tokenText(sentence: SentenceAnalysis, id: number): string {
  return sentence.tokens.find((t) => t.id === id)?.form ?? "";
}

export function spanText(sentence: SentenceAnalysis, first: number, last: number): string {
  return sentence.tokens
    .filter((t) => t.id >= first && t.id <= last)
    .map((t) => t.form)
    .join(" ");
}
