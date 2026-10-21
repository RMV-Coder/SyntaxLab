import type { ConstituencyAnalysis, ConstituencyNode, Token } from "@/lib/api/types";

/** Width in px of `text` when drawn as a node label or as a word. */
export type Measure = (text: string, kind: "label" | "word") => number;

export interface ConstituencyLayoutOptions {
  levelHeight: number;
  leafGap: number;
  wordOffset: number;
  padding: number;
}

const DEFAULTS: ConstituencyLayoutOptions = {
  levelHeight: 58,
  leafGap: 20,
  wordOffset: 34,
  padding: 28,
};

export type LaidNodeKind = "phrase" | "preterminal" | "collapsed";

export interface LaidNode {
  id: string;
  label: string;
  kind: LaidNodeKind;
  x: number;
  y: number;
  depth: number;
  /** Word ids dominated by this node (inclusive span, in order). */
  tokenIds: number[];
  /** Word (pre-terminal) or covered text (collapsed phrase) drawn below the node. */
  text: string | null;
  /** Width reserved for `text` (used for the triangle of a collapsed phrase). */
  textWidth: number;
  /** True if the node is a phrase in the full tree, i.e. it can be collapsed/expanded. */
  collapsible: boolean;
  parentId: string | null;
}

export interface LaidEdge {
  from: string;
  to: string;
}

export interface ConstituencyLayout {
  nodes: LaidNode[];
  edges: LaidEdge[];
  width: number;
  height: number;
  leafY: number;
  wordY: number;
}

/**
 * Lays out a constituency tree in the style of syntax textbooks: words on a single baseline in
 * sentence order, pre-terminals (or collapsed phrases) directly above them, and each phrase
 * centred over the span of its first and last child.
 *
 * Collapsed phrases become leaves whose covered words are drawn under a triangle, the usual
 * notation for a constituent whose internal structure is not shown.
 */
export function layoutConstituency(
  tree: ConstituencyAnalysis,
  tokens: Token[],
  collapsed: ReadonlySet<string>,
  measure: Measure,
  options: Partial<ConstituencyLayoutOptions> = {},
): ConstituencyLayout {
  const opts = { ...DEFAULTS, ...options };
  const byId = new Map<string, ConstituencyNode>(tree.nodes.map((n) => [n.id, n]));
  const formOf = new Map<number, string>(tokens.map((t) => [t.id, t.form]));

  interface Draft {
    node: ConstituencyNode;
    depth: number;
    children: Draft[];
    leafKind: LaidNodeKind | null;
    parentId: string | null;
  }

  const build = (id: string, depth: number, parentId: string | null): Draft => {
    const node = byId.get(id);
    if (!node) throw new Error(`unknown constituency node ${id}`);
    if (node.token_id != null) {
      return { node, depth, children: [], leafKind: "preterminal", parentId };
    }
    if (collapsed.has(id)) return { node, depth, children: [], leafKind: "collapsed", parentId };
    return {
      node,
      depth,
      children: node.children.map((c) => build(c, depth + 1, id)),
      leafKind: null,
      parentId,
    };
  };

  const root = build(tree.root, 0, null);

  const leaves: Draft[] = [];
  let maxDepth = 0;
  const collectLeaves = (d: Draft) => {
    maxDepth = Math.max(maxDepth, d.depth);
    if (d.leafKind) leaves.push(d);
    d.children.forEach(collectLeaves);
  };
  collectLeaves(root);

  const leafY = opts.padding + maxDepth * opts.levelHeight;
  const wordY = leafY + opts.wordOffset;
  const spanIds = (n: ConstituencyNode) => {
    const [first, last] = n.span;
    return Array.from({ length: last - first + 1 }, (_, i) => first + i);
  };
  const leafText = (d: Draft) =>
    spanIds(d.node)
      .map((id) => formOf.get(id) ?? "")
      .join(" ");

  const xOf = new Map<string, number>();
  const textWidthOf = new Map<string, number>();
  let cursor = opts.padding;
  for (const leaf of leaves) {
    const text = leafText(leaf);
    const textWidth = measure(text, "word");
    const width = Math.max(measure(leaf.node.label, "label"), textWidth);
    xOf.set(leaf.node.id, cursor + width / 2);
    textWidthOf.set(leaf.node.id, textWidth);
    cursor += width + opts.leafGap;
  }
  const width = Math.max(cursor - opts.leafGap + opts.padding, opts.padding * 2);

  const nodes: LaidNode[] = [];
  const edges: LaidEdge[] = [];
  const place = (d: Draft): number => {
    let x: number;
    if (d.leafKind) {
      x = xOf.get(d.node.id) ?? 0;
    } else {
      const childXs = d.children.map(place);
      x = (childXs[0] + childXs[childXs.length - 1]) / 2;
      for (const c of d.children) edges.push({ from: d.node.id, to: c.node.id });
    }
    nodes.push({
      id: d.node.id,
      label: d.node.label,
      kind: d.leafKind ?? "phrase",
      x,
      // Pre-terminals sit on the leaf row; a collapsed phrase keeps its own level so its
      // triangle spans down to the words, as in textbook trees.
      y: d.leafKind === "preterminal" ? leafY : opts.padding + d.depth * opts.levelHeight,
      depth: d.depth,
      tokenIds: spanIds(d.node),
      text: d.leafKind ? leafText(d) : null,
      textWidth: textWidthOf.get(d.node.id) ?? 0,
      collapsible: d.node.token_id == null,
      parentId: d.parentId,
    });
    return x;
  };
  place(root);

  return { nodes, edges, width, height: wordY + opts.padding, leafY, wordY };
}

/** Labelled bracketing, e.g. "[S [NP [DT The] [NN child]] ...]", as an accessible text form. */
export function toBracketNotation(tree: ConstituencyAnalysis, tokens: Token[]): string {
  const byId = new Map(tree.nodes.map((n) => [n.id, n]));
  const formOf = new Map(tokens.map((t) => [t.id, t.form]));
  const render = (id: string): string => {
    const n = byId.get(id);
    if (!n) return "";
    if (n.token_id != null) return `[${n.label} ${formOf.get(n.token_id) ?? ""}]`;
    return `[${n.label} ${n.children.map(render).join(" ")}]`;
  };
  return render(tree.root);
}

/** Ids of all phrase nodes (collapsible), for "collapse all" style operations. */
export function phraseNodeIds(tree: ConstituencyAnalysis): string[] {
  return tree.nodes.filter((n) => n.token_id == null && n.id !== tree.root).map((n) => n.id);
}
