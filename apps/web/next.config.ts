import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const apiUrl = process.env.NEXT_PUBLIC_SYNTAXLAB_API_URL ?? "http://127.0.0.1:8710";
const apiOrigin = new URL(apiUrl).origin;

/**
 * Who may show SyntaxLab in a frame: the developer's portfolio embeds the live analyzer as its
 * SyntaxLab exhibit (localhost for working on that page). SyntaxLab has no accounts and nothing a
 * click could change, so this is safe. Extra origins, space-separated, in SYNTAXLAB_FRAME_ANCESTORS.
 */
const frameAncestors = [
  "'self'",
  "https://raymondvaldepenas-dev.vercel.app",
  "http://localhost:3000",
  ...(process.env.SYNTAXLAB_FRAME_ANCESTORS ?? "").split(/\s+/).filter(Boolean),
].join(" ");

/**
 * Static Content-Security-Policy (no nonces, so pages stay prerendered; see the Next.js
 * "Content Security Policy > Without Nonces" guide). Network access is limited to this site and
 * the parser API. `blob:`/`data:` images are needed for PNG export of diagrams.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  `frame-ancestors ${frameAncestors}`,
  // Only when the API itself is served over HTTPS (i.e. a real deployment).
  ...(apiOrigin.startsWith("https://") ? ["upgrade-insecure-requests"] : []),
].join("; ");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // No X-Frame-Options: it can only allow everyone or no one, and frame-ancestors above
          // replaces it in every current browser.
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
