import type { Metadata } from "next";
import { GraphWorkspace } from "../components/graph-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Node graph",
};

export default function GraphPage() {
  return (
    <WorkspaceShell title="Evidence graph" eyebrow="ENC-07 · Rex">
      <GraphWorkspace />
    </WorkspaceShell>
  );
}
