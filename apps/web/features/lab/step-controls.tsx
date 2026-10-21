"use client";

import { ChevronFirst, ChevronLast, Pause, Play, StepBack, StepForward } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const SPEEDS = { slow: 1, normal: 3, fast: 10 } as const;
export type Speed = keyof typeof SPEEDS;

interface StepControlsProps {
  step: number;
  last: number;
  playing: boolean;
  speed: Speed;
  onStep: (step: number) => void;
  onPlayingChange: (playing: boolean) => void;
  onSpeedChange: (speed: Speed) => void;
}

function Control({
  label,
  shortcut,
  onClick,
  disabled,
  children,
}: {
  label: string;
  shortcut?: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-9"
          aria-label={label}
          aria-keyshortcuts={shortcut}
          onClick={onClick}
          disabled={disabled}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {label}
        {shortcut ? ` (${shortcut.replace("Arrow", "")})` : ""}
      </TooltipContent>
    </Tooltip>
  );
}

export function StepControls({
  step,
  last,
  playing,
  speed,
  onStep,
  onPlayingChange,
  onSpeedChange,
}: StepControlsProps) {
  const atEnd = step >= last;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <div className="flex items-center" role="toolbar" aria-label="Replay controls">
        <Control label="Reset" shortcut="Home" onClick={() => onStep(0)} disabled={step === 0}>
          <ChevronFirst />
        </Control>
        <Control label="Step back" shortcut="ArrowLeft" onClick={() => onStep(step - 1)} disabled={step === 0}>
          <StepBack />
        </Control>
        <Control
          label={playing ? "Pause" : atEnd ? "Replay from the start" : "Play"}
          onClick={() => {
            if (atEnd && !playing) onStep(0);
            onPlayingChange(!playing);
          }}
        >
          {playing ? <Pause /> : <Play />}
        </Control>
        <Control label="Step forward" shortcut="ArrowRight" onClick={() => onStep(step + 1)} disabled={atEnd}>
          <StepForward />
        </Control>
        <Control label="Jump to the end" shortcut="End" onClick={() => onStep(last)} disabled={atEnd}>
          <ChevronLast />
        </Control>
      </div>
      <div className="flex min-w-48 flex-1 items-center gap-2 text-xs text-graphite">
        <input
          type="range"
          min={0}
          max={last}
          value={step}
          onChange={(e) => onStep(Number(e.target.value))}
          className="h-1 flex-1 cursor-pointer accent-[var(--ink)]"
          aria-label="Step"
          aria-valuetext={`Step ${step + 1} of ${last + 1}`}
        />
        <span className="w-24 text-right tabular-nums text-ink-soft">
          {step + 1} / {last + 1}
        </span>
      </div>
      <Select value={speed} onValueChange={(v) => onSpeedChange(v as Speed)}>
        <SelectTrigger size="sm" className="w-28 bg-sheet" aria-label="Playback speed">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="slow">Slow</SelectItem>
          <SelectItem value="normal">Normal</SelectItem>
          <SelectItem value="fast">Fast</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
