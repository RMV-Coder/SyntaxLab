import type { Metadata } from "next";

import { ExerciseListPage } from "@/features/learn/learn-pages";

export const metadata: Metadata = { title: "Practice" };

export default function LearnPage() {
  return <ExerciseListPage />;
}
