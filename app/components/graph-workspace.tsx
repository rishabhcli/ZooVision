"use client";

import { Maximize2, Minimize2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { GraphStage } from "./graph-stage";

export function GraphWorkspace() {
  const frameRef = useRef<HTMLElement>(null);
  const [nativeFullscreen, setNativeFullscreen] = useState(false);
  const [fallbackExpanded, setFallbackExpanded] = useState(false);
  const expanded = nativeFullscreen || fallbackExpanded;

  useEffect(() => {
    const updateFullscreenState = () => {
      setNativeFullscreen(document.fullscreenElement === frameRef.current);
    };
    document.addEventListener("fullscreenchange", updateFullscreenState);
    return () =>
      document.removeEventListener("fullscreenchange", updateFullscreenState);
  }, []);

  useEffect(() => {
    if (!fallbackExpanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeExpandedView = (event: KeyboardEvent) => {
      if (event.key === "Escape") setFallbackExpanded(false);
    };
    document.addEventListener("keydown", closeExpandedView);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeExpandedView);
    };
  }, [fallbackExpanded]);

  async function toggleFullscreen() {
    if (fallbackExpanded) {
      setFallbackExpanded(false);
      return;
    }
    if (document.fullscreenElement === frameRef.current) {
      await document.exitFullscreen();
      return;
    }
    const frame = frameRef.current;
    if (!frame?.requestFullscreen) {
      setFallbackExpanded(true);
      return;
    }
    try {
      await frame.requestFullscreen();
      if (document.fullscreenElement !== frame) setFallbackExpanded(true);
    } catch {
      setFallbackExpanded(true);
    }
  }

  return (
    <div className="node-evidence-page">
      <section
        className="node-evidence-frame"
        data-expanded={fallbackExpanded || undefined}
        ref={frameRef}
      >
        <header className="node-evidence-bar">
          <span>
            <strong>Neo4j video context graph</strong>
            <i>·</i>
            Backend connected evidence
          </span>
          <button
            type="button"
            aria-label={expanded ? "Exit expanded graph" : "Expand evidence graph"}
            title={expanded ? "Exit fullscreen" : "View graph fullscreen"}
            onClick={() => void toggleFullscreen()}
          >
            {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </header>
        <GraphStage />
      </section>
    </div>
  );
}
