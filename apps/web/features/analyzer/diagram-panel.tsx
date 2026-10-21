"use client";

import {
  Download,
  Expand,
  ImageDown,
  Maximize2,
  RotateCcw,
  Tags,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useId, useMemo, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { SentenceAnalysis, StructureKind } from "@/lib/api/types";
import { exportFileName, exportPngFile, exportSvgFile } from "@/lib/export/svg-export";
import { layoutConstituency, toBracketNotation } from "@/lib/syntax/constituency-layout";
import { layoutDependency } from "@/lib/syntax/dependency-layout";
import { theme } from "@/lib/theme";

import { ConstituencyDiagram } from "./constituency-diagram";
import { ARROW_DEFS, DependencyDiagram } from "./dependency-diagram";
import { useDiagramFonts, useMeasure } from "./hooks";
import type { Glossaries } from "./inspector";
import { InterlinearStrip } from "./interlinear-strip";
import type { Highlight, Selection } from "./selection";
import { ZoomableSvg, type ZoomHandle } from "./zoomable-svg";

const VIEW_NAMES: Record<StructureKind, string> = {
  constituency: "Phrase structure",
  dependency: "Word relations",
};

interface DiagramPanelProps {
  /** Code of the analyzed language, set as `lang` on the sentence for assistive technology. */
  language: string;
  sentence: SentenceAnalysis;
  view: StructureKind;
  views: StructureKind[];
  onViewChange: (view: StructureKind) => void;
  highlight: Highlight;
  selection: Selection;
  glossaries: Glossaries;
  collapsed: ReadonlySet<string>;
  onSelect: (selection: Selection) => void;
  onToggle: (nodeId: string) => void;
  onExpandAll: () => void;
}

function ToolButton({
  label,
  onClick,
  children,
  pressed,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  pressed?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={label}
          aria-pressed={pressed}
          onClick={onClick}
          className="size-8 text-ink-soft aria-pressed:bg-muted aria-pressed:text-ink"
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function DiagramPanel({
  language,
  sentence,
  view,
  views,
  onViewChange,
  highlight,
  selection,
  glossaries,
  collapsed,
  onSelect,
  onToggle,
  onExpandAll,
}: DiagramPanelProps) {
  const zoom = useRef<ZoomHandle>(null);
  const { fonts, ready } = useDiagramFonts();
  const measure = useMeasure(fonts, ready);
  const [showLabels, setShowLabels] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const helpId = useId();

  const constituency = useMemo(
    () =>
      sentence.constituency
        ? layoutConstituency(sentence.constituency, sentence.tokens, collapsed, measure)
        : null,
    [sentence, collapsed, measure],
  );
  const dependency = useMemo(
    () =>
      sentence.dependency
        ? layoutDependency(sentence.tokens, sentence.dependency.arcs, (t, k) =>
            k === "word" ? measure(t, "word") : measure(t, "label") * 0.9,
          )
        : null,
    [sentence, measure],
  );

  const size =
    view === "constituency" && constituency
      ? { width: constituency.width, height: constituency.height }
      : dependency
        ? { width: dependency.width, height: dependency.height }
        : { width: 0, height: 0 };

  const exportAs = async (format: "svg" | "png") => {
    const svg = zoom.current?.svg();
    if (!svg) return;
    setExportError(null);
    const options = {
      ...size,
      background: theme.sheet,
      title: `${VIEW_NAMES[view]}: ${sentence.text}`,
    };
    const name = exportFileName(sentence.text, view, format);
    try {
      if (format === "svg") await exportSvgFile(svg, options, [fonts.data, fonts.ui], name);
      else await exportPngFile(svg, options, [fonts.data, fonts.ui], name);
    } catch {
      setExportError("The image could not be exported in this browser.");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-3 py-2">
        {views.length > 1 ? (
          <Tabs value={view} onValueChange={(v) => onViewChange(v as StructureKind)}>
            <TabsList>
              {views.map((v) => (
                <TabsTrigger key={v} value={v}>
                  {VIEW_NAMES[v] ?? v}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        ) : (
          <h2 className="px-1 text-sm font-semibold">{VIEW_NAMES[view] ?? view}</h2>
        )}
        <div className="flex items-center gap-0.5" role="toolbar" aria-label="Diagram tools">
          <ToolButton label="Zoom in" onClick={() => zoom.current?.zoomIn()}>
            <ZoomIn />
          </ToolButton>
          <ToolButton label="Zoom out" onClick={() => zoom.current?.zoomOut()}>
            <ZoomOut />
          </ToolButton>
          <ToolButton label="Fit to screen" onClick={() => zoom.current?.fit()}>
            <Maximize2 />
          </ToolButton>
          <ToolButton label="Reset view" onClick={() => zoom.current?.reset()}>
            <RotateCcw />
          </ToolButton>
          {view === "dependency" ? (
            <ToolButton
              label={showLabels ? "Hide relation labels" : "Show relation labels"}
              pressed={showLabels}
              onClick={() => setShowLabels((s) => !s)}
            >
              <Tags />
            </ToolButton>
          ) : (
            <ToolButton label="Expand all phrases" onClick={onExpandAll}>
              <Expand />
            </ToolButton>
          )}
          <span className="mx-1 h-5 w-px bg-rule" aria-hidden />
          <ToolButton label="Download as SVG" onClick={() => void exportAs("svg")}>
            <Download />
          </ToolButton>
          <ToolButton label="Download as PNG" onClick={() => void exportAs("png")}>
            <ImageDown />
          </ToolButton>
        </div>
      </div>

      <div className="relative min-h-[18rem] flex-1 bg-sheet" data-testid="diagram-canvas" lang={language}>
        <ZoomableSvg
          ref={zoom}
          width={size.width}
          height={size.height}
          label={`${VIEW_NAMES[view]} of “${sentence.text}”`}
          describedBy={helpId}
          onBackgroundClick={() => onSelect(null)}
          defs={ARROW_DEFS}
        >
          {view === "constituency" && constituency ? (
            <ConstituencyDiagram
              layout={constituency}
              sentence={sentence}
              highlight={highlight}
              selection={selection}
              fonts={fonts}
              phraseGlossary={glossaries.constituency}
              posGlossary={glossaries.pos}
              onSelect={onSelect}
              onToggle={onToggle}
              onHover={setHover}
            />
          ) : null}
          {view === "dependency" && dependency ? (
            <DependencyDiagram
              layout={dependency}
              sentence={sentence}
              highlight={highlight}
              selection={selection}
              fonts={fonts}
              showLabels={showLabels}
              relationGlossary={glossaries.dependency}
              posGlossary={glossaries.pos}
              onSelect={onSelect}
              onHover={setHover}
            />
          ) : null}
        </ZoomableSvg>
        <p
          id={helpId}
          className="pointer-events-none absolute bottom-2 left-3 right-3 truncate text-xs text-graphite"
        >
          {hover ??
            (view === "constituency"
              ? "Arrow keys follow the branches. Enter selects; C or double-click collapses a phrase."
              : "Arrow keys: left/right between words, up to the head, down to a dependent. Enter selects.")}
        </p>
      </div>
      {exportError ? (
        <p role="alert" className="border-t border-rule px-3 py-1.5 text-xs text-destructive">
          {exportError}
        </p>
      ) : null}

      {view === "constituency" && sentence.constituency ? (
        <p className="sr-only">
          Bracketed structure: {toBracketNotation(sentence.constituency, sentence.tokens)}
        </p>
      ) : null}

      <div className="border-t border-rule bg-sheet px-3 py-3" lang={language}>
        <InterlinearStrip
          sentence={sentence}
          highlight={highlight}
          selection={selection}
          posGlossary={glossaries.pos}
          featureGlossary={glossaries.features}
          onSelect={onSelect}
        />
      </div>
    </div>
  );
}
