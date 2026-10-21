"use client";

import { useMemo, useState, type KeyboardEvent } from "react";

import type { Glossary, SentenceAnalysis } from "@/lib/api/types";
import type { DependencyLayout } from "@/lib/syntax/dependency-layout";
import { lookupLabel, posFamily } from "@/lib/syntax/glossary";
import { posColor, theme } from "@/lib/theme";

import { DIAGRAM_TYPE, type DiagramFonts } from "./hooks";
import type { Highlight, Selection } from "./selection";

interface DependencyDiagramProps {
  layout: DependencyLayout;
  sentence: SentenceAnalysis;
  highlight: Highlight;
  selection: Selection;
  fonts: DiagramFonts;
  showLabels: boolean;
  relationGlossary: Glossary | undefined;
  posGlossary: Glossary | undefined;
  onSelect: (selection: Selection) => void;
  onHover: (text: string | null) => void;
}

export const ARROW_DEFS = (
  <>
    <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0,0 L8,4 L0,8 Z" fill={theme.graphite} />
    </marker>
    <marker
      id="arrow-strong"
      viewBox="0 0 8 8"
      refX="7"
      refY="4"
      markerWidth="7"
      markerHeight="7"
      orient="auto"
    >
      <path d="M0,0 L8,4 L0,8 Z" fill={theme.ink} />
    </marker>
  </>
);

const SMALL_CAPS = { fontVariantCaps: "all-small-caps", letterSpacing: "0.03em" } as const;

export function DependencyDiagram({
  layout,
  sentence,
  highlight,
  selection,
  fonts,
  showLabels,
  relationGlossary,
  posGlossary,
  onSelect,
  onHover,
}: DependencyDiagramProps) {
  const tokenById = useMemo(() => new Map(sentence.tokens.map((t) => [t.id, t])), [sentence]);
  const arcByDependent = useMemo(
    () => new Map((sentence.dependency?.arcs ?? []).map((a) => [a.dependent, a])),
    [sentence],
  );
  const [focusId, setFocusId] = useState<number | null>(null);
  const activeId =
    focusId ?? (selection?.kind === "token" ? selection.id : (sentence.tokens[0]?.id ?? null));

  const relationName = (relation: string) => {
    const { entry } = lookupLabel(relationGlossary, relation);
    return entry ? `${relation}: ${entry.name}` : relation;
  };

  const onKey = (event: KeyboardEvent, id: number) => {
    const ids = sentence.tokens.map((t) => t.id);
    let next: number | undefined;
    switch (event.key) {
      case "ArrowLeft":
        next = ids[ids.indexOf(id) - 1];
        break;
      case "ArrowRight":
        next = ids[ids.indexOf(id) + 1];
        break;
      case "ArrowUp": {
        const head = arcByDependent.get(id)?.head;
        next = head && head > 0 ? head : undefined;
        break;
      }
      case "ArrowDown":
        next = sentence.dependency?.arcs.find((a) => a.head === id)?.dependent;
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        onSelect({ kind: "token", id });
        return;
      default:
        return;
    }
    event.preventDefault();
    if (next) {
      setFocusId(next);
      document.getElementById(`dtok-${next}`)?.focus();
    }
  };

  return (
    <g fontFamily={fonts.data} fill={theme.ink}>
      {layout.arcs.map((arc) => {
        const strong = highlight.arcs.has(arc.dependent);
        const selected = selection?.kind === "arc" && selection.dependent === arc.dependent;
        const labelWidth = arc.relation.length * 6.6 + 10;
        const select = (e: { stopPropagation: () => void }) => {
          e.stopPropagation();
          onSelect({ kind: "arc", dependent: arc.dependent });
        };
        return (
          <g
            key={arc.dependent}
            className="cursor-pointer"
            onClick={select}
            onMouseEnter={() =>
              onHover(
                `${relationName(arc.relation)}. “${tokenById.get(arc.dependent)?.form}” depends on “${tokenById.get(arc.head)?.form}”.`,
              )
            }
            onMouseLeave={() => onHover(null)}
          >
            <path d={arc.path} fill="none" stroke="transparent" strokeWidth={10} data-export="exclude" />
            <path
              d={arc.path}
              fill="none"
              stroke={strong || selected ? theme.ink : theme.graphite}
              strokeWidth={strong || selected ? 2 : 1.2}
              markerEnd={strong || selected ? "url(#arrow-strong)" : "url(#arrow)"}
            />
            {showLabels ? (
              <g>
                <rect
                  x={arc.labelX - labelWidth / 2}
                  y={arc.labelY - 9}
                  width={labelWidth}
                  height={18}
                  rx={3}
                  fill={selected ? theme.highlight : strong ? theme.highlightSoft : theme.sheet}
                />
                <text
                  x={arc.labelX}
                  y={arc.labelY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontFamily={fonts.ui}
                  fontSize={DIAGRAM_TYPE.relation.size}
                  fontWeight={DIAGRAM_TYPE.relation.weight}
                  fill={strong || selected ? theme.ink : theme.inkSoft}
                >
                  {arc.relation}
                </text>
              </g>
            ) : null}
            <title>{relationName(arc.relation)}</title>
          </g>
        );
      })}

      {layout.root ? (
        <g>
          <line
            x1={layout.root.x}
            y1={layout.root.top + 14}
            x2={layout.root.x}
            y2={layout.baseY}
            stroke={highlight.tokens.has(layout.root.tokenId) ? theme.ink : theme.graphite}
            strokeWidth={1.2}
            markerEnd="url(#arrow)"
          />
          <text
            x={layout.root.x}
            y={layout.root.top + 4}
            textAnchor="middle"
            fontFamily={fonts.ui}
            fontSize={DIAGRAM_TYPE.relation.size}
            fill={theme.inkSoft}
          >
            root
          </text>
        </g>
      ) : null}

      {layout.tokens.map((laid) => {
        const token = tokenById.get(laid.id)!;
        const marked = highlight.tokens.has(laid.id);
        const selected = selection?.kind === "token" && selection.id === laid.id;
        const family = posFamily(posGlossary, token.upos);
        const arc = arcByDependent.get(laid.id);
        return (
          <g
            key={laid.id}
            id={`dtok-${laid.id}`}
            role="button"
            tabIndex={laid.id === activeId ? 0 : -1}
            aria-pressed={selected}
            aria-label={`${token.form}, ${token.upos ?? "no tag"}${arc ? `, ${arc.relation}` : ""}`}
            className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[var(--ink)]"
            onClick={(e) => {
              e.stopPropagation();
              setFocusId(laid.id);
              onSelect({ kind: "token", id: laid.id });
            }}
            onKeyDown={(e) => onKey(e, laid.id)}
            onFocus={() => setFocusId(laid.id)}
          >
            <rect
              data-export={marked ? undefined : "exclude"}
              x={laid.x - laid.width / 2 - 5}
              y={layout.wordY - 13}
              width={laid.width + 10}
              height={46}
              rx={4}
              fill={selected ? theme.highlight : marked ? theme.highlightSoft : "transparent"}
              stroke="transparent"
              strokeWidth={2}
            />
            <text
              x={laid.x}
              y={layout.wordY}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={DIAGRAM_TYPE.word.size}
            >
              {token.form}
            </text>
            <text
              x={laid.x}
              y={layout.tagY}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={DIAGRAM_TYPE.tagLabel.size}
              fontWeight={DIAGRAM_TYPE.tagLabel.weight}
              fill={posColor(family)}
              style={SMALL_CAPS}
            >
              {token.upos ?? ""}
            </text>
          </g>
        );
      })}
    </g>
  );
}
