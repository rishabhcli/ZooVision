import type { Metadata } from "next";
import { ReviewWorkspace } from "../components/review-workspace";
import { WorkspaceShell } from "../components/workspace-shell";

export const metadata: Metadata = {
  title: "Review queue",
};

export default function ReviewPage() {
  return (
    <WorkspaceShell title="Review queue" eyebrow="Keeper operations">
      <ReviewWorkspace />
    </WorkspaceShell>
  );
}
