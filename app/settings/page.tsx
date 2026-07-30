import type { Metadata } from "next";
import { SettingsWorkspace } from "../components/settings-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <WorkspaceShell title="Workspace settings" eyebrow="This device">
      <SettingsWorkspace />
    </WorkspaceShell>
  );
}
