import type { Metadata } from "next";
import { MonitorWorkspace } from "../components/monitor-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Monitor",
};

export default function MonitorPage() {
  return (
    <WorkspaceShell title="Camera review" eyebrow="ENC-07 · Camera 2">
      <MonitorWorkspace />
    </WorkspaceShell>
  );
}
