import { TooltipProvider } from "@/components/ui/tooltip";
import { AnalyzerWorkspace } from "@/features/analyzer/analyzer-workspace";

export default function AnalyzerPage() {
  return (
    <>
      <h1 className="sr-only">Sentence analyzer</h1>
      {/* Tooltips are only used by the workspaces: keep Radix Tooltip out of other pages. */}
      <TooltipProvider delayDuration={300}>
        <AnalyzerWorkspace />
      </TooltipProvider>
    </>
  );
}
