"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

/** Unexpected rendering errors. API errors are handled where they happen, with specific messages. */
export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-xl px-5 py-16">
      <h1 className="font-data text-3xl font-bold text-ink">This page stopped working</h1>
      <p className="mt-3 leading-relaxed text-ink-soft">
        Something unexpected went wrong while showing this page. Try again, or reload the page.
      </p>
      <Button className="mt-6" onClick={retry}>
        Try again
      </Button>
    </div>
  );
}
