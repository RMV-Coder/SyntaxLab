/**
 * Colour and type values for SVG drawing. SVG diagrams use literal values (not CSS variables)
 * so that exported SVG/PNG files render identically outside the app. Keep in sync with the
 * tokens in app/globals.css.
 */
export const theme = {
  paper: "#f6f7f9",
  sheet: "#ffffff",
  ink: "#18233a",
  inkSoft: "#3a4660",
  graphite: "#5b6577",
  rule: "#d5dae2",
  highlight: "#f5cf4a",
  highlightSoft: "#fbeab0",
  pos: {
    nominal: "#1f5fa8",
    verbal: "#a23b24",
    modifier: "#2e7d4f",
    function: "#6b4fa0",
    other: "#5b6577",
  },
  /** Font stacks with fallbacks that keep exported diagrams readable without web fonts. */
  fontData: "'Gentium Book Plus', 'Gentium Plus', Georgia, 'Times New Roman', serif",
  fontUi: "'IBM Plex Sans', 'Segoe UI', Helvetica, Arial, sans-serif",
} as const;

export type PosFamily = keyof typeof theme.pos;

export function posColor(family: string | null | undefined): string {
  return family && family in theme.pos ? theme.pos[family as PosFamily] : theme.pos.other;
}
