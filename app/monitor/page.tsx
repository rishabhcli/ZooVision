import type { Metadata } from "next";
import { MonitorWorkspace } from "../components/monitor-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Monitor",
};

export default function MonitorPage() {
  return (
    <WorkspaceShell
      title="Overnight evidence workspace"
      eyebrow="May 12, 2025"
    >
      <MonitorWorkspace />
    </WorkspaceShell>
  );
}
