import { describe, expect, it } from "vitest";

import {
  exportFileName,
  familiesIn,
  parseUnicodeRange,
  rangeCovers,
  serializeSvg,
} from "./svg-export";

function diagram(): SVGSVGElement {
  const host = document.createElement("div");
  host.innerHTML = `
    <svg class="interactive" role="img" aria-label="tree" style="cursor:grab">
      <g data-zoom-layer transform="translate(40,10) scale(2)">
        <text>&lt;script&gt;alert(1)&lt;/script&gt; &amp; Ñoño</text>
        <circle data-export="exclude" r="4"></circle>
      </g>
    </svg>`;
  return host.querySelector("svg")!;
}

describe("serializeSvg", () => {
  const out = serializeSvg(diagram(), {
    width: 200.4,
    height: 100,
    background: "#ffffff",
    css: "@font-face{font-family:x}",
    title: "SyntaxLab tree",
  });

  it("produces a standalone SVG document with dimensions and viewBox", () => {
    expect(out.startsWith('<?xml version="1.0" encoding="UTF-8"?>')).toBe(true);
    expect(out).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(out).toContain('width="201"');
    expect(out).toContain('viewBox="0 0 201 100"');
  });

  it("exports the full diagram, not the zoomed viewport", () => {
    expect(out).not.toContain("translate(40,10)");
  });

  it("drops interactive-only elements and attributes", () => {
    expect(out).not.toContain("<circle");
    expect(out).not.toContain("cursor:grab");
    expect(out).not.toContain('role="img"');
  });

  it("embeds background, CSS and title", () => {
    expect(out).toContain('fill="#ffffff"');
    expect(out).toContain("@font-face{font-family:x}");
    expect(out).toContain("<title>SyntaxLab tree</title>");
  });

  it("keeps user text escaped and Unicode intact", () => {
    expect(out).toContain("&lt;script&gt;alert(1)&lt;/script&gt; &amp; Ñoño");
    expect(out).not.toContain("<script>");
  });

  it("does not modify the on-screen diagram", () => {
    const svg = diagram();
    serializeSvg(svg, { width: 10, height: 10, background: "#fff" });
    expect(svg.querySelector("[data-zoom-layer]")?.getAttribute("transform")).toContain("scale(2)");
    expect(svg.querySelector("circle")).not.toBeNull();
  });
});

describe("familiesIn", () => {
  it("extracts unquoted family names from font stacks", () => {
    expect(familiesIn(["'Gentium Book Plus', Georgia, serif", '"IBM Plex Sans", sans-serif'])).toEqual(
      new Set(["Gentium Book Plus", "Georgia", "serif", "IBM Plex Sans", "sans-serif"]),
    );
  });
});

describe("exportFileName", () => {
  it("builds a safe slug from the sentence", () => {
    expect(exportFileName("I saw the man with a telescope.", "constituency", "svg")).toBe(
      "syntaxlab-constituency-i-saw-the-man-with-a-telescope.svg",
    );
    expect(exportFileName("Señor Ñoño's café!", "dependency", "png")).toBe(
      "syntaxlab-dependency-senor-nono-s-cafe.png",
    );
    expect(exportFileName("日本語", "dependency", "png")).toBe("syntaxlab-dependency.png");
  });
});

describe("unicode-range filtering", () => {
  it("parses single code points, ranges and wildcards", () => {
    expect(parseUnicodeRange("U+0-FF, U+131, U+4??")).toEqual([
      [0, 0xff],
      [0x131, 0x131],
      [0x400, 0x4ff],
    ]);
  });

  it("selects only subsets covering the diagram's characters", () => {
    const latin = "U+0-FF, U+131, U+152-153";
    const cyrillic = "U+400-45F, U+490-491";
    expect(rangeCovers(latin, "The child is eating rice.")).toBe(true);
    expect(rangeCovers(cyrillic, "The child is eating rice.")).toBe(false);
    expect(rangeCovers(cyrillic, "Привет")).toBe(true);
    expect(rangeCovers("", "anything")).toBe(true);
  });
});
