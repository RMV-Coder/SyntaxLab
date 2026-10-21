/**
 * Per-browser exercise progress (localStorage). A convenience only: SyntaxLab has no accounts,
 * so progress never leaves this device and may be cleared by the browser at any time.
 */
const KEY = "syntaxlab.learn.progress.v1";

export interface ExerciseProgress {
  solved: boolean;
  best: number; // 0..1
}

export type ProgressMap = Record<string, ExerciseProgress>;

export function readProgress(): ProgressMap {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? (parsed as ProgressMap) : {};
  } catch {
    return {};
  }
}

export function recordProgress(id: string, score: number, solved: boolean): ProgressMap {
  const all = readProgress();
  const previous = all[id];
  all[id] = {
    solved: solved || Boolean(previous?.solved),
    best: Math.max(score, previous?.best ?? 0),
  };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    // Storage may be unavailable (private mode, quota); progress is optional.
  }
  return all;
}
