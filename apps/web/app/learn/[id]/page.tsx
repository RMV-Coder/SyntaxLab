import type { Metadata } from "next";
import { Suspense } from "react";

import { ExercisePage } from "@/features/learn/learn-pages";

export const metadata: Metadata = { title: "Exercise" };

// With cacheComponents enabled, request-time params must be read inside a Suspense boundary
// so the rest of the page can be prerendered.
async function Exercise({ params }: { params: PageProps<"/learn/[id]">["params"] }) {
  const { id } = await params;
  return <ExercisePage id={id} />;
}

export default function LearnExercisePage(props: PageProps<"/learn/[id]">) {
  return (
    <Suspense fallback={<p className="mx-auto max-w-4xl px-5 py-8 text-sm text-graphite">Loading…</p>}>
      <Exercise params={props.params} />
    </Suspense>
  );
}
