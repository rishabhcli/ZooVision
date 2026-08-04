import type { Metadata } from "next";
import { ReportsWorkspace } from "../components/reports-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Morning reports",
};

export default function ReportsPage() {
  return (
    <WorkspaceShell title="Morning reports" eyebrow="Keeper operations">
      <ReportsWorkspace />
    </WorkspaceShell>
  );
}
