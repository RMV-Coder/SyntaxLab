import type { Metadata } from "next";

import { LabWorkspace } from "@/features/lab/lab-workspace";

export const metadata: Metadata = { title: "Algorithm Lab" };

export default function LabPage() {
  return (
    <>
      <h1 className="sr-only">Algorithm Lab: the Earley parser step by step</h1>
      <LabWorkspace />
    </>
  );
}
