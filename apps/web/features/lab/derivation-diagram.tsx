"use client";

import type { DerivationLayout } from "@/lib/syntax/derivation-layout";
import { theme } from "@/lib/theme";

import { DIAGRAM_TYPE, type DiagramFonts } from "../analyzer/hooks";

interface DerivationDiagramProps {
  layout: DerivationLayout;
  fonts: DiagramFonts;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** A parse tree from the Earley parser. Grammar symbols are shown exactly as written. */
export function DerivationDiagram({ layout, fonts, selectedId, onSelect }: DerivationDiagramProps) {
  const byId = new Map(layout.nodes.map((n) => [n.id, n]));
  const selected = selectedId ? byId.get(selectedId) : undefined;
  const inSpan = (start: number, end: number) =>
    selected != null && selected.kind === "nonterminal" && start >= selected.start && end <= selected.end && end > start;

  return (
    <g fontFamily={fonts.data} fill={theme.ink}>
      {layout.edges.map((e) => {
        const from = byId.get(e.from)!;
        const to = byId.get(e.to)!;
        return (
          <line
            key={`${e.from}-${e.to}`}
            x1={from.x}
            y1={from.y + 10}
            x2={to.x}
            y2={to.y - 13}
            stroke={theme.graphite}
            strokeWidth={1.2}
            strokeLinecap="round"
          />
        );
      })}
      {layout.nodes.map((node) => {
        if (node.kind === "nonterminal") {
          const isSelected = node.id === selectedId;
          const width = Math.max(28, node.label.length * 10 + 14);
          return (
            <g
              key={node.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={`${node.label}, words ${node.start + 1} to ${node.end}`}
              className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[var(--ink)]"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(node.id);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(node.id);
                }
              }}
            >
              <rect
                x={node.x - width / 2}
                y={node.y - 13}
                width={width}
                height={26}
                rx={4}
                fill={isSelected ? theme.highlight : "transparent"}
                stroke="transparent"
                strokeWidth={2}
              />
              <text
                x={node.x}
                y={node.y}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={DIAGRAM_TYPE.phraseLabel.size}
                fontWeight={700}
              >
                {node.label}
              </text>
            </g>
          );
        }
        const marked = node.kind === "word" && inSpan(node.start, node.end);
        return (
          <g key={node.id}>
            {marked ? (
              <rect
                x={node.x - node.label.length * 4.6 - 5}
                y={node.y - 12}
                width={node.label.length * 9.2 + 10}
                height={24}
                rx={3}
                fill={theme.highlightSoft}
              />
            ) : null}
            <text
              x={node.x}
              y={node.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={DIAGRAM_TYPE.word.size}
              fontStyle={node.kind === "empty" ? "italic" : undefined}
              fill={node.kind === "empty" ? theme.graphite : theme.ink}
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}
