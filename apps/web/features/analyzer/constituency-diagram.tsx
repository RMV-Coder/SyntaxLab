"use client";

import { useMemo, useState, type KeyboardEvent } from "react";

import type { Glossary, SentenceAnalysis } from "@/lib/api/types";
import type { ConstituencyLayout, LaidNode } from "@/lib/syntax/constituency-layout";
import { lookupLabel, posFamily } from "@/lib/syntax/glossary";
import { posColor, theme } from "@/lib/theme";

import { DIAGRAM_TYPE, type DiagramFonts } from "./hooks";
import type { Highlight, Selection } from "./selection";

interface ConstituencyDiagramProps {
  layout: ConstituencyLayout;
  sentence: SentenceAnalysis;
  highlight: Highlight;
  selection: Selection;
  fonts: DiagramFonts;
  phraseGlossary: Glossary | undefined;
  posGlossary: Glossary | undefined;
  onSelect: (selection: Selection) => void;
  onToggle: (nodeId: string) => void;
  onHover: (text: string | null) => void;
}

const SMALL_CAPS = { fontVariantCaps: "all-small-caps", letterSpacing: "0.02em" } as const;

export function ConstituencyDiagram({
  layout,
  sentence,
  highlight,
  selection,
  fonts,
  phraseGlossary,
  posGlossary,
  onSelect,
  onToggle,
  onHover,
}: ConstituencyDiagramProps) {
  const byId = useMemo(() => new Map(layout.nodes.map((n) => [n.id, n])), [layout]);
  const childrenOf = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const e of layout.edges) map.set(e.from, [...(map.get(e.from) ?? []), e.to]);
    return map;
  }, [layout]);
  const tokenById = useMemo(() => new Map(sentence.tokens.map((t) => [t.id, t])), [sentence]);
  const rootId = layout.nodes.find((n) => n.parentId === null)?.id ?? null;
  const [focusId, setFocusId] = useState<string | null>(null);
  const activeId =
    focusId && byId.has(focusId)
      ? focusId
      : selection?.kind === "node" && byId.has(selection.id)
        ? selection.id
        : rootId;

  const describe = (node: LaidNode) => {
    const { entry } = lookupLabel(phraseGlossary, node.label);
    return entry ? `${node.label}: ${entry.name}` : node.label;
  };

  const move = (event: KeyboardEvent, node: LaidNode) => {
    const siblings = node.parentId ? (childrenOf.get(node.parentId) ?? []) : [node.id];
    const index = siblings.indexOf(node.id);
    let next: string | undefined;
    switch (event.key) {
      case "ArrowUp":
        next = node.parentId ?? undefined;
        break;
      case "ArrowDown":
        next = childrenOf.get(node.id)?.[0];
        break;
      case "ArrowLeft":
        next = siblings[index - 1];
        break;
      case "ArrowRight":
        next = siblings[index + 1];
        break;
      case "Home":
        next = rootId ?? undefined;
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        onSelect({ kind: "node", id: node.id });
        return;
      case "c":
      case "C":
        if (node.collapsible && node.parentId) onToggle(node.id);
        return;
      default:
        return;
    }
    event.preventDefault();
    if (next) {
      setFocusId(next);
      document.getElementById(`cnode-${next}`)?.focus();
    }
  };

  const labelHalfHeight = 9;

  return (
    <g fontFamily={fonts.data} fill={theme.ink}>
      {/* edges */}
      {layout.edges.map((e) => {
        const from = byId.get(e.from)!;
        const to = byId.get(e.to)!;
        const onPath = highlight.nodes.has(e.from) && highlight.nodes.has(e.to);
        return (
          <line
            key={`${e.from}-${e.to}`}
            x1={from.x}
            y1={from.y + labelHalfHeight}
            x2={to.x}
            y2={to.y - labelHalfHeight - 4}
            stroke={onPath ? theme.ink : theme.graphite}
            strokeWidth={onPath ? 2.2 : 1.2}
            strokeLinecap="round"
          />
        );
      })}

      {layout.nodes.map((node) => {
        const isSelected = selection?.kind === "node" && selection.id === node.id;
        const emphasized = highlight.nodes.has(node.id);
        const token = node.kind === "preterminal" ? tokenById.get(node.tokenIds[0]) : undefined;
        const family = token ? posFamily(posGlossary, token.upos) : null;
        const labelColor = node.kind === "preterminal" ? posColor(family) : theme.ink;
        const spec = node.kind === "phrase" ? DIAGRAM_TYPE.phraseLabel : DIAGRAM_TYPE.tagLabel;
        const labelWidth = Math.max(26, node.label.length * spec.size * 0.62 + 12);
        const wordsHighlighted = node.tokenIds.every((id) => highlight.tokens.has(id));
        return (
          <g key={node.id}>
            <g
              id={`cnode-${node.id}`}
              role="button"
              tabIndex={node.id === activeId ? 0 : -1}
              aria-pressed={isSelected}
              aria-label={`${describe(node)}, covering “${node.text ?? spanOf(sentence, node)}”`}
              className="cursor-pointer outline-none [&:focus-visible>rect.focus]:stroke-[var(--ink)]"
              onClick={(e) => {
                e.stopPropagation();
                setFocusId(node.id);
                onSelect({ kind: "node", id: node.id });
              }}
              onDoubleClick={(e) => {
                e.stopPropagation();
                if (node.collapsible && node.parentId) onToggle(node.id);
              }}
              onKeyDown={(e) => move(e, node)}
              onFocus={() => setFocusId(node.id)}
              onMouseEnter={() => onHover(describe(node))}
              onMouseLeave={() => onHover(null)}
            >
              <rect
                className="focus"
                data-export={isSelected || emphasized ? undefined : "exclude"}
                x={node.x - labelWidth / 2}
                y={node.y - 13}
                width={labelWidth}
                height={26}
                rx={4}
                fill={isSelected ? theme.highlight : emphasized ? theme.highlightSoft : "transparent"}
                stroke="transparent"
                strokeWidth={2}
              />
              <text
                x={node.x}
                y={node.y}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={spec.size}
                fontWeight={spec.weight}
                fill={labelColor}
                style={SMALL_CAPS}
              >
                {node.label}
              </text>
              <title>{describe(node)}</title>
            </g>

            {node.kind === "preterminal" && token ? (
              <g
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect({ kind: "token", id: token.id });
                }}
              >
                <line
                  x1={node.x}
                  y1={node.y + labelHalfHeight + 2}
                  x2={node.x}
                  y2={layout.wordY - 13}
                  stroke={theme.rule}
                  strokeWidth={1}
                />
                {wordsHighlighted ? (
                  <rect
                    x={node.x - node.textWidth / 2 - 4}
                    y={layout.wordY - 12}
                    width={node.textWidth + 8}
                    height={24}
                    rx={3}
                    fill={theme.highlightSoft}
                  />
                ) : null}
                <text
                  x={node.x}
                  y={layout.wordY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={DIAGRAM_TYPE.word.size}
                >
                  {token.form}
                </text>
              </g>
            ) : null}

            {node.kind === "collapsed" ? (
              <g>
                <polygon
                  points={`${node.x},${node.y + labelHalfHeight + 2} ${node.x - node.textWidth / 2},${layout.wordY - 14} ${node.x + node.textWidth / 2},${layout.wordY - 14}`}
                  fill={wordsHighlighted ? theme.highlightSoft : "none"}
                  stroke={theme.graphite}
                  strokeWidth={1.2}
                  strokeLinejoin="round"
                />
                <text
                  x={node.x}
                  y={layout.wordY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={DIAGRAM_TYPE.word.size}
                >
                  {node.text}
                </text>
              </g>
            ) : null}
          </g>
        );
      })}
    </g>
  );
}

function spanOf(sentence: SentenceAnalysis, node: LaidNode): string {
  return sentence.tokens
    .filter((t) => node.tokenIds.includes(t.id))
    .map((t) => t.form)
    .join(" ");
}
