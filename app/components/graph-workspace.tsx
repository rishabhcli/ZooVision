"use client";

import { Maximize2 } from "lucide-react";
import { GraphStage } from "./graph-stage";

export function GraphWorkspace() {
  return (
    <div className="node-evidence-page">
      <section className="node-evidence-frame">
        <header className="node-evidence-bar">
          <span>
            <strong>Evidence graph</strong>
            <i>·</i>
            Savannah Overlook
            <i>·</i>
            May 12, 2025
          </span>
          <button type="button" aria-label="Expand evidence graph">
            <Maximize2 size={15} />
          </button>
        </header>
        <GraphStage />
      </section>
    </div>
  );
}
