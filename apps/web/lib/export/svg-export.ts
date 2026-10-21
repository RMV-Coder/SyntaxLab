/**
 * Export of diagrams as standalone SVG and PNG.
 *
 * The exported image is the whole diagram as currently displayed (including collapsed
 * phrases), independent of the current zoom/pan viewport. Fonts used by the diagram are
 * embedded as data URLs so labels render identically outside the app; if embedding fails the
 * SVG still names readable fallback fonts (see lib/theme.ts).
 */

export interface ExportOptions {
  width: number;
  height: number;
  background: string;
  /** Extra CSS (typically @font-face rules) to embed. */
  css?: string;
  title?: string;
}

const SVG_NS = "http://www.w3.org/2000/svg";

/** Produce a standalone SVG document string from a rendered diagram. */
export function serializeSvg(svg: SVGSVGElement, options: ExportOptions): string {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.querySelectorAll("[data-export='exclude']").forEach((el) => el.remove());
  // Undo the interactive zoom/pan transform: export the full diagram.
  clone.querySelectorAll("[data-zoom-layer]").forEach((el) => el.removeAttribute("transform"));
  for (const attr of ["class", "style", "tabindex", "role", "aria-label", "aria-describedby"]) {
    clone.removeAttribute(attr);
  }
  clone.setAttribute("xmlns", SVG_NS);
  clone.setAttribute("width", String(Math.ceil(options.width)));
  clone.setAttribute("height", String(Math.ceil(options.height)));
  clone.setAttribute("viewBox", `0 0 ${Math.ceil(options.width)} ${Math.ceil(options.height)}`);

  const doc = clone.ownerDocument;
  const background = doc.createElementNS(SVG_NS, "rect");
  background.setAttribute("width", "100%");
  background.setAttribute("height", "100%");
  background.setAttribute("fill", options.background);
  clone.insertBefore(background, clone.firstChild);

  if (options.css) {
    const style = doc.createElementNS(SVG_NS, "style");
    style.textContent = options.css;
    clone.insertBefore(style, clone.firstChild);
  }
  if (options.title) {
    const title = doc.createElementNS(SVG_NS, "title");
    title.textContent = options.title;
    clone.insertBefore(title, clone.firstChild);
  }
  // XMLSerializer escapes text content, so user-provided words cannot inject markup.
  return `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(clone)}`;
}

function unquote(family: string): string {
  return family.trim().replace(/^["']|["']$/g, "");
}

/** Font family names (first entry of each stack) that appear in a font-family value list. */
export function familiesIn(stacks: string[]): Set<string> {
  return new Set(stacks.flatMap((s) => s.split(",").map(unquote)).filter(Boolean));
}

async function toDataUrl(url: string): Promise<string> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`font fetch failed: ${response.status}`);
  const blob = await response.blob();
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** Parse a CSS unicode-range value ("U+0-FF, U+131, U+2000-206F") into inclusive ranges. */
export function parseUnicodeRange(value: string): [number, number][] {
  return value
    .split(",")
    .map((part) => part.trim().replace(/^U\+/i, ""))
    .filter(Boolean)
    .map((part) => {
      if (part.includes("?")) {
        return [parseInt(part.replace(/\?/g, "0"), 16), parseInt(part.replace(/\?/g, "F"), 16)];
      }
      const [lo, hi] = part.split("-");
      return [parseInt(lo, 16), parseInt(hi ?? lo, 16)];
    })
    .filter(([lo, hi]) => Number.isFinite(lo) && Number.isFinite(hi)) as [number, number][];
}

/** True if any character of `text` falls inside the unicode-range (an empty range covers all). */
export function rangeCovers(value: string, text: string): boolean {
  if (!value.trim()) return true;
  const ranges = parseUnicodeRange(value);
  for (const ch of text) {
    const cp = ch.codePointAt(0)!;
    if (ranges.some(([lo, hi]) => cp >= lo && cp <= hi)) return true;
  }
  return false;
}

/**
 * Collect @font-face rules for the given families from same-origin stylesheets, inlined as
 * data URLs. Only upright faces whose unicode-range covers characters in `text` are embedded,
 * which keeps exported files small (one or two subsets for most sentences).
 */
export async function collectFontFaceCss(families: Set<string>, text: string): Promise<string> {
  const rules: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let cssRules: CSSRuleList;
    try {
      cssRules = sheet.cssRules;
    } catch {
      continue; // cross-origin stylesheet
    }
    for (const rule of Array.from(cssRules)) {
      if (!(rule instanceof CSSFontFaceRule)) continue;
      const family = unquote(rule.style.getPropertyValue("font-family"));
      if (!families.has(family)) continue;
      if (/italic|oblique/.test(rule.style.getPropertyValue("font-style"))) continue;
      if (!rangeCovers(rule.style.getPropertyValue("unicode-range"), text)) continue;
      const src = rule.style.getPropertyValue("src");
      const match = /url\(["']?([^"')]+)["']?\)/.exec(src);
      if (!match) continue;
      try {
        const absolute = new URL(match[1], sheet.href ?? document.baseURI).href;
        const data = await toDataUrl(absolute);
        const descriptors = ["font-weight", "font-style", "unicode-range"]
          .map((d) => [d, rule.style.getPropertyValue(d)] as const)
          .filter(([, v]) => v)
          .map(([d, v]) => `${d}:${v};`)
          .join("");
        rules.push(`@font-face{font-family:"${family}";src:url(${data});${descriptors}}`);
      } catch {
        // Keep exporting; fallback fonts in the diagram's font stacks remain readable.
      }
    }
  }
  return rules.join("\n");
}

function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function exportSvgFile(
  svg: SVGSVGElement,
  options: ExportOptions,
  fontStacks: string[],
  filename: string,
): Promise<void> {
  const css = await collectFontFaceCss(familiesIn(fontStacks), svg.textContent ?? "");
  const text = serializeSvg(svg, { ...options, css: [options.css, css].filter(Boolean).join("\n") });
  download(new Blob([text], { type: "image/svg+xml;charset=utf-8" }), filename);
}

export async function exportPngFile(
  svg: SVGSVGElement,
  options: ExportOptions,
  fontStacks: string[],
  filename: string,
  scale = 2,
): Promise<void> {
  const css = await collectFontFaceCss(familiesIn(fontStacks), svg.textContent ?? "");
  const text = serializeSvg(svg, { ...options, css: [options.css, css].filter(Boolean).join("\n") });
  const url = URL.createObjectURL(new Blob([text], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.decoding = "async";
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("could not rasterize the diagram"));
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(options.width * scale);
    canvas.height = Math.ceil(options.height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("canvas is not available");
    context.scale(scale, scale);
    context.drawImage(image, 0, 0, options.width, options.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("could not encode PNG");
    download(blob, filename);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** A safe file name derived from the analyzed sentence. */
export function exportFileName(text: string, view: string, extension: "svg" | "png"): string {
  const slug = text
    .normalize("NFKD")
    .replace(/\p{M}/gu, "") // strip combining marks (accents)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return `syntaxlab-${view}${slug ? `-${slug}` : ""}.${extension}`;
}
