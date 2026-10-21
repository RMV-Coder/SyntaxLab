"use client"; // Error boundaries must be Client Components

/**
 * Errors in the root layout itself. This replaces the whole document, so it cannot rely on the
 * app's fonts or stylesheet: styles are inline and use the same colours as the app.
 */
export default function GlobalError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          background: "#f6f7f9",
          color: "#18233a",
          fontFamily: "Georgia, 'Times New Roman', serif",
        }}
      >
        <title>SyntaxLab: something went wrong</title>
        <main style={{ maxWidth: "36rem", margin: "0 auto", padding: "4rem 1.25rem" }}>
          <h1 style={{ fontSize: "1.875rem", margin: 0 }}>SyntaxLab could not load</h1>
          <p style={{ lineHeight: 1.6, color: "#3a4660" }}>
            Something unexpected went wrong. Try again, or reload the page.
          </p>
          <button
            type="button"
            onClick={retry}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 1rem",
              border: 0,
              borderRadius: "0.375rem",
              background: "#18233a",
              color: "#ffffff",
              font: "inherit",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
