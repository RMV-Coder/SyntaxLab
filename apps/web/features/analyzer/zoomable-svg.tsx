"use client";

import { select } from "d3-selection";
import "d3-transition"; // adds selection.transition()
import { zoom as d3zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import { useCallback, useEffect, useImperativeHandle, useRef, type ReactNode, type Ref } from "react";

export interface ZoomHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  reset: () => void;
  svg: () => SVGSVGElement | null;
}

interface ZoomableSvgProps {
  /** Natural size of the diagram content. */
  width: number;
  height: number;
  label: string;
  describedBy?: string;
  children: ReactNode;
  ref?: Ref<ZoomHandle>;
  onBackgroundClick?: () => void;
  defs?: ReactNode;
}

const MIN_SCALE = 0.25;
const MAX_SCALE = 4;

/**
 * Pan/zoom surface. React renders the diagram; d3-zoom only maintains the transform of the
 * `data-zoom-layer` group. Wheel/pinch zoom, drag to pan; toolbar buttons call the handle.
 */
export function ZoomableSvg({
  width,
  height,
  label,
  describedBy,
  children,
  ref,
  onBackgroundClick,
  defs,
}: ZoomableSvgProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const layerRef = useRef<SVGGElement>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const behavior = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([MIN_SCALE, MAX_SCALE])
      .on("zoom", (event: { transform: { toString(): string } }) => {
        layerRef.current?.setAttribute("transform", event.transform.toString());
      });
    zoomRef.current = behavior;
    select(svg).call(behavior).on("dblclick.zoom", null);
    return () => {
      select(svg).on(".zoom", null);
    };
  }, []);

  const apply = useCallback((transform: typeof zoomIdentity) => {
    const svg = svgRef.current;
    const behavior = zoomRef.current;
    if (!svg || !behavior) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const selection = select(svg);
    if (reduced) selection.call(behavior.transform, transform);
    else selection.transition().duration(250).call(behavior.transform, transform);
  }, []);

  const fit = useCallback(() => {
    const svg = svgRef.current;
    if (!svg || width <= 0 || height <= 0) return;
    const { width: cw, height: ch } = svg.getBoundingClientRect();
    if (cw === 0 || ch === 0) return;
    const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.min(cw / width, ch / height, 1.6) * 0.96));
    apply(zoomIdentity.translate((cw - width * scale) / 2, (ch - height * scale) / 2).scale(scale));
  }, [apply, width, height]);

  useImperativeHandle(
    ref,
    () => ({
      zoomIn: () => svgRef.current && zoomRef.current?.scaleBy(select(svgRef.current), 1.25),
      zoomOut: () => svgRef.current && zoomRef.current?.scaleBy(select(svgRef.current), 0.8),
      fit,
      reset: () => apply(zoomIdentity),
      svg: () => svgRef.current,
    }),
    [apply, fit],
  );

  // Fit whenever new content arrives.
  useEffect(() => {
    fit();
  }, [fit]);

  return (
    <svg
      ref={svgRef}
      className="h-full w-full touch-none select-none"
      role="group"
      aria-label={label}
      aria-describedby={describedBy}
      onClick={(e) => {
        if (e.target === svgRef.current) onBackgroundClick?.();
      }}
    >
      {defs ? <defs>{defs}</defs> : null}
      <g ref={layerRef} data-zoom-layer="">
        {children}
      </g>
    </svg>
  );
}
