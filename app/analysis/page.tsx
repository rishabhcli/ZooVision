import type { Metadata } from "next";
import { AnalysisWorkspace } from "../components/analysis-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Analysis",
};

export default function AnalysisPage() {
  return (
    <WorkspaceShell title="Overnight analysis" eyebrow="May 12, 2025">
      <AnalysisWorkspace />
    </WorkspaceShell>
  );
}
