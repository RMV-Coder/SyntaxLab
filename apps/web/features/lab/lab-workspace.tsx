"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, ApiError } from "@/lib/api/client";
import type {
  GrammarPresetDetail,
  GrammarPresetSummary,
  ParseGrammarResponse,
  ValidateGrammarResponse,
} from "@/lib/api/types";
import { derivationBrackets, layoutDerivation } from "@/lib/syntax/derivation-layout";
import { cn } from "@/lib/utils";

import { useDiagramFonts, useMeasure } from "../analyzer/hooks";
import { ZoomableSvg } from "../analyzer/zoomable-svg";
import { ChartView } from "./chart-view";
import { DerivationDiagram } from "./derivation-diagram";
import { completionStep, explainEvent, ruleOf, type EventTone } from "./replay";
import { SPEEDS, StepControls, type Speed } from "./step-controls";

type Panel = "grammar" | "steps" | "result";

const TONE: Record<EventTone, string> = {
  start: "border-ink",
  progress: "border-ink",
  duplicate: "border-rule-strong",
  rejected: "border-destructive",
  accepted: "border-pos-modifier",
};

// ------------------------------------------------------------------ data hooks

function usePresets() {
  const [presets, setPresets] = useState<GrammarPresetSummary[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api
      .grammarPresets(controller.signal)
      .then((r) => setPresets(r.presets))
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e);
      });
    return () => controller.abort();
  }, []);
  return { presets, error };
}

/** Validates the grammar as the user types (debounced). */
function useValidation(grammar: string) {
  const [result, setResult] = useState<ValidateGrammarResponse | null>(null);
  useEffect(() => {
    if (!grammar.trim()) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .validateGrammar(grammar, controller.signal)
        .then(setResult)
        .catch(() => undefined);
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [grammar]);
  return grammar.trim() ? result : null;
}

// ------------------------------------------------------------------ grammar panel

function GrammarPanel({
  presets,
  preset,
  grammar,
  edited,
  validation,
  sentence,
  busy,
  onPreset,
  onGrammar,
  onSentence,
  onRun,
}: {
  presets: GrammarPresetSummary[];
  preset: GrammarPresetDetail | null;
  grammar: string;
  edited: boolean;
  validation: ValidateGrammarResponse | null;
  sentence: string;
  busy: boolean;
  onPreset: (id: string) => void;
  onGrammar: (text: string) => void;
  onSentence: (text: string) => void;
  onRun: (sentence?: string) => void;
}) {
  const ids = { preset: useId(), grammar: useId(), sentence: useId(), problems: useId() };
  const editor = useRef<HTMLTextAreaElement>(null);
  const errors = validation?.diagnostics.filter((d) => d.severity === "error") ?? [];
  const warnings = validation?.diagnostics.filter((d) => d.severity === "warning") ?? [];
  const summary = validation?.grammar;
  const canRun = Boolean(validation?.valid) && sentence.trim().length > 0 && !busy;

  const goToLine = (line: number | null) => {
    const el = editor.current;
    if (!el || line == null) return;
    const lines = el.value.split("\n");
    const start = lines.slice(0, line - 1).reduce((n, l) => n + l.length + 1, 0);
    el.focus();
    el.setSelectionRange(start, start + (lines[line - 1]?.length ?? 0));
  };

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor={ids.preset}>Grammar</Label>
        <Select value={preset?.id} onValueChange={onPreset} disabled={!presets.length}>
          <SelectTrigger id={ids.preset} className="w-full bg-sheet">
            <SelectValue placeholder="Loading grammars…" />
          </SelectTrigger>
          <SelectContent>
            {presets.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {preset ? <p className="text-xs leading-relaxed text-ink-soft">{preset.description}</p> : null}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <Label htmlFor={ids.grammar}>Rules</Label>
          {edited && preset ? (
            <button type="button" className="text-xs text-ink-soft underline" onClick={() => onPreset(preset.id)}>
              Restore preset
            </button>
          ) : null}
        </div>
        <textarea
          id={ids.grammar}
          ref={editor}
          value={grammar}
          onChange={(e) => onGrammar(e.target.value)}
          spellCheck={false}
          wrap="off"
          rows={12}
          aria-describedby={ids.problems}
          aria-invalid={errors.length > 0}
          className="w-full resize-y rounded-md border border-input bg-sheet px-3 py-2 font-mono text-[0.8125rem] leading-relaxed text-ink"
        />
        <div id={ids.problems} aria-live="polite" className="space-y-1 text-xs">
          {errors.map((d, i) => (
            <button key={`e${i}`} type="button" onClick={() => goToLine(d.line)} className="block text-left text-destructive">
              {d.line ? `Line ${d.line}: ` : ""}
              {d.message}
            </button>
          ))}
          {warnings.map((d, i) => (
            <button key={`w${i}`} type="button" onClick={() => goToLine(d.line)} className="block text-left text-graphite">
              {d.line ? `Line ${d.line}: ` : ""}
              {d.message}
            </button>
          ))}
          {validation?.valid && summary ? (
            <p className="text-graphite">
              {summary.rules.length - 1} rules, {summary.nonterminals.length} categories,{" "}
              {summary.terminals.length} words. Start symbol {summary.start}.
              {summary.nullable.length ? ` Can be empty: ${summary.nullable.join(", ")}.` : ""}
            </p>
          ) : null}
          <p className="text-graphite">
            Notation: <code>NP -&gt; Det N | &quot;she&quot;</code>, words in quotes, ε for an empty rule. This is
            a small teaching grammar, not a grammar of English.
          </p>
        </div>
      </div>

      <form
        className="space-y-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (canRun) onRun();
        }}
      >
        <Label htmlFor={ids.sentence}>Sentence</Label>
        <div className="flex gap-2">
          <input
            id={ids.sentence}
            value={sentence}
            onChange={(e) => onSentence(e.target.value)}
            spellCheck={false}
            className="min-w-0 flex-1 rounded-md border border-input bg-sheet px-3 py-2 font-data text-base text-ink"
          />
          <Button type="submit" disabled={!canRun}>
            {busy ? "Parsing…" : "Parse"}
          </Button>
        </div>
      </form>

      {preset?.examples.length ? (
        <div className="space-y-2">
          <h2 className="text-sm font-medium">Examples</h2>
          <ul className="space-y-1">
            {preset.examples.map((ex) => (
              <li key={ex.text}>
                <button
                  type="button"
                  disabled={busy || !validation?.valid}
                  onClick={() => {
                    onSentence(ex.text);
                    onRun(ex.text);
                  }}
                  className="w-full rounded-md px-2 py-1.5 text-left hover:bg-muted disabled:opacity-60"
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="font-data text-[0.9375rem] text-ink">{ex.text}</span>
                    {!edited ? (
                      <span className="shrink-0 text-xs text-graphite">
                        {ex.expect.accepted
                          ? `${ex.expect.parses} parse${ex.expect.parses === 1 ? "" : "s"}`
                          : "rejected"}
                      </span>
                    ) : null}
                  </span>
                  {ex.note ? <span className="mt-0.5 block text-xs text-graphite">{ex.note}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ result panel

function ResultPanel({
  response,
  revealed,
  onReveal,
  onJump,
}: {
  response: ParseGrammarResponse;
  revealed: boolean;
  onReveal: () => void;
  onJump: (step: number) => void;
}) {
  const [index, setIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { fonts, ready } = useDiagramFonts();
  const measure = useMeasure(fonts, ready);
  const tree = response.trees[Math.min(index, response.trees.length - 1)];
  const layout = useMemo(() => (tree ? layoutDerivation(tree, measure) : null), [tree, measure]);
  const selected = layout?.nodes.find((n) => n.id === selectedId) ?? null;

  if (!revealed) {
    return (
      <div className="space-y-3 text-sm text-ink-soft">
        <p>The outcome appears when the replay reaches the end, so you can follow the algorithm first.</p>
        <Button variant="outline" size="sm" onClick={onReveal}>
          Show the outcome now
        </Button>
      </div>
    );
  }

  const step = selected?.tree ? completionStep(response, selected.tree) : null;
  return (
    <div className="space-y-4">
      <div>
        <p className={cn("font-data text-2xl font-bold", response.accepted ? "text-pos-modifier" : "text-destructive")}>
          {response.accepted ? "Accepted" : "Rejected"}
        </p>
        <p className="mt-1 text-sm text-ink-soft">
          {response.accepted
            ? response.tree_count === 1
              ? "One parse tree: this grammar gives the sentence a single structure."
              : `${response.tree_count_capped ? "More than " : ""}${response.tree_count.toLocaleString("en")} parse trees: the sentence is ambiguous under this grammar.`
            : "The grammar does not generate this sentence."}
          {response.trees.length < response.tree_count ? ` Showing the first ${response.trees.length}.` : ""}
        </p>
        {response.unknown_tokens.length ? (
          <p className="mt-1 text-sm text-destructive">
            No rule produces {response.unknown_tokens.map((i) => `“${response.tokens[i]}”`).join(", ")}.
          </p>
        ) : null}
      </div>

      {tree && layout ? (
        <div className="space-y-2">
          {response.trees.length > 1 ? (
            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Previous tree"
                disabled={index === 0}
                onClick={() => {
                  setIndex(index - 1);
                  setSelectedId(null);
                }}
              >
                <ChevronLeft />
              </Button>
              <span className="text-sm tabular-nums" aria-live="polite">
                Tree {index + 1} of {response.trees.length}
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Next tree"
                disabled={index >= response.trees.length - 1}
                onClick={() => {
                  setIndex(index + 1);
                  setSelectedId(null);
                }}
              >
                <ChevronRight />
              </Button>
            </div>
          ) : null}
          <div className="h-72 rounded-md border border-rule bg-sheet" data-testid="lab-tree">
            <ZoomableSvg width={layout.width} height={layout.height} label={`Parse tree ${index + 1}`} onBackgroundClick={() => setSelectedId(null)}>
              <DerivationDiagram layout={layout} fonts={fonts} selectedId={selectedId} onSelect={setSelectedId} />
            </ZoomableSvg>
          </div>
          <p className="break-words font-data text-xs text-graphite">{derivationBrackets(tree)}</p>
          {selected?.tree && selected.rule != null ? (
            <div className="rounded-md bg-muted p-3 text-sm" aria-live="polite">
              <p>
                <span className="font-semibold">{selected.label}</span> covers{" "}
                {selected.start === selected.end
                  ? "no words (it is empty)"
                  : `“${response.tokens.slice(selected.start, selected.end).join(" ")}”`}
                , built with the rule <span className="font-data">{ruleOf(response, selected.rule).text}</span>.
              </p>
              {step != null ? (
                <Button variant="outline" size="sm" className="mt-2" onClick={() => onJump(step)}>
                  Show the step where it was completed
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="text-xs text-graphite">Select a category in the tree to see the rule that built it.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ workspace

export function LabWorkspace() {
  const { presets, error: presetsError } = usePresets();
  const [preset, setPreset] = useState<GrammarPresetDetail | null>(null);
  const [grammar, setGrammar] = useState("");
  const [sentence, setSentence] = useState("");
  const [response, setResponse] = useState<ParseGrammarResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>("normal");
  const [revealed, setRevealed] = useState(false);
  const [panel, setPanel] = useState<Panel>("grammar");
  const validation = useValidation(grammar);
  const edited = preset != null && grammar !== preset.grammar;

  const loadPreset = useCallback((id: string) => {
    void api.grammarPreset(id).then((detail) => {
      setPreset(detail);
      setGrammar(detail.grammar);
      setSentence(detail.examples[0]?.text ?? "");
      setResponse(null);
    });
  }, []);

  // Load the first preset once the list arrives.
  const firstPreset = presets[0]?.id;
  useEffect(() => {
    if (firstPreset) loadPreset(firstPreset);
  }, [firstPreset, loadPreset]);

  const last = response ? response.trace.length - 1 : 0;
  const goTo = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(last, next));
      setStep(clamped);
      if (clamped >= last) setRevealed(true);
    },
    [last],
  );

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setStep((s) => {
        if (s >= last) {
          setPlaying(false);
          setRevealed(true);
          return s;
        }
        if (s + 1 >= last) setRevealed(true);
        return s + 1;
      });
    }, 1000 / SPEEDS[speed]);
    return () => clearInterval(timer);
  }, [playing, speed, last]);

  const run = (text?: string) => {
    setBusy(true);
    setError(null);
    setPlaying(false);
    api
      .parseWithGrammar({ grammar, sentence: text ?? sentence, max_trees: 20 })
      .then((r) => {
        setResponse(r);
        setStep(0);
        setRevealed(false);
        setPanel("steps");
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e);
      })
      .finally(() => setBusy(false));
  };

  const event = response ? response.trace[Math.min(step, last)] : null;
  const explanation = response && event ? explainEvent(response, event) : null;

  // Replay shortcuts work anywhere on the page (except while typing), so they keep working when
  // the focused control becomes disabled, e.g. "Step forward" at the last step.
  useEffect(() => {
    if (!response) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (target?.closest("input, textarea, select, [role=combobox], [role=listbox], [role=slider]")) return;
      const moves: Record<string, number> = {
        ArrowRight: step + 1,
        ArrowLeft: step - 1,
        Home: 0,
        End: last,
      };
      if (e.key in moves) {
        e.preventDefault();
        setPlaying(false);
        goTo(moves[e.key]);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [response, step, last, goTo]);

  const tabs: { id: Panel; label: string }[] = [
    { id: "grammar", label: "Grammar" },
    { id: "steps", label: "Steps" },
    { id: "result", label: "Result" },
  ];

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <nav aria-label="Lab panels" className="flex border-b border-rule bg-sheet lg:hidden">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-pressed={panel === t.id}
            onClick={() => setPanel(t.id)}
            className={cn(
              "flex-1 border-b-2 px-3 py-2.5 text-sm font-medium",
              panel === t.id ? "border-ink text-ink" : "border-transparent text-graphite",
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] lg:grid-cols-[24rem_minmax(0,1fr)_25rem]">
        <aside
          aria-label="Grammar and sentence"
          className={cn("min-h-0 overflow-y-auto border-rule bg-paper p-5 lg:block lg:border-r", panel !== "grammar" && "hidden")}
        >
          {presetsError ? (
            <p role="alert" className="text-sm text-destructive">
              {presetsError.message}
            </p>
          ) : (
            <GrammarPanel
              presets={presets}
              preset={preset}
              grammar={grammar}
              edited={edited}
              validation={validation}
              sentence={sentence}
              busy={busy}
              onPreset={loadPreset}
              onGrammar={setGrammar}
              onSentence={setSentence}
              onRun={run}
            />
          )}
        </aside>

        <section
          aria-label="Algorithm steps"
          className={cn("min-h-0 min-w-0 flex-col lg:flex", panel === "steps" ? "flex" : "hidden")}
        >
          {error ? (
            <p role="alert" className="border-b border-rule p-3 text-sm text-destructive">
              {error.message}
            </p>
          ) : null}
          {response && explanation && event ? (
            <>
              <div className="space-y-3 border-b border-rule bg-sheet px-4 py-3">
                <StepControls
                  step={step}
                  last={last}
                  playing={playing}
                  speed={speed}
                  onStep={(s) => {
                    setPlaying(false);
                    goTo(s);
                  }}
                  onPlayingChange={setPlaying}
                  onSpeedChange={setSpeed}
                />
                <p className="font-data text-lg text-ink">
                  {response.tokens.map((t, i) => (
                    <span key={i} className={cn("mr-1.5 inline-block", event.token === i && "rounded-sm bg-highlight px-0.5")}>
                      <span className="mr-1 align-super font-sans text-[0.625rem] text-graphite">{i}</span>
                      {t}
                    </span>
                  ))}
                  <span className="align-super font-sans text-[0.625rem] text-graphite">{response.tokens.length}</span>
                </p>
                <div className={cn("border-l-4 pl-3", TONE[explanation.tone])} aria-live="polite" data-testid="step-explanation">
                  <p className="text-sm font-semibold text-ink">
                    Step {step + 1}: {explanation.title}
                  </p>
                  <p className="text-sm leading-relaxed text-ink-soft">{explanation.body}</p>
                </div>
                {response.trace_truncated ? (
                  <p className="text-xs text-destructive">
                    The trace is too long to show in full; the replay stops early. The outcome is complete.
                  </p>
                ) : null}
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto bg-sheet">
                <ChartView response={response} step={step} event={event} />
              </div>
            </>
          ) : (
            <div className="mx-auto flex h-full max-w-xl flex-col justify-center px-6 py-12">
              <p className="font-data text-3xl leading-snug text-ink">Watch a parser work, one step at a time.</p>
              <p className="mt-4 leading-relaxed text-ink-soft">
                The Earley algorithm reads a sentence from left to right. At each position it{" "}
                <em>predicts</em> which rules could start there, <em>scans</em> the next word, and{" "}
                <em>completes</em> phrases it has finished, recording everything in a chart.
              </p>
              <p className="mt-3 leading-relaxed text-ink-soft">
                Pick a grammar and an example, then press Parse. Every step you see was recorded while
                the parser actually ran.
              </p>
            </div>
          )}
        </section>

        <aside
          aria-label="Result"
          className={cn("min-h-0 overflow-y-auto border-rule bg-sheet p-5 lg:block lg:border-l", panel !== "result" && "hidden")}
        >
          {response ? (
            <ResultPanel
              key={`${response.tokens.join(" ")}:${response.trace.length}:${response.grammar.rules.length}`}
              response={response}
              revealed={revealed}
              onReveal={() => goTo(last)}
              onJump={(s) => {
                setPlaying(false);
                goTo(s);
                setPanel("steps");
              }}
            />
          ) : (
            <p className="text-sm text-graphite">The outcome and the parse trees appear here.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
