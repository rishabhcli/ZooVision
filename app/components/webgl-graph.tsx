"use client";

import Graph from "graphology";
import {
  Activity,
  BarChart3,
  Bookmark,
  CalendarDays,
  Camera,
  CheckCircle2,
  CircleUserRound,
  Clock3,
  ExternalLink,
  Focus,
  Minus,
  MoreVertical,
  Play,
  Plus,
  ShieldCheck,
  Video,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import Sigma from "sigma";

type NodeKind = "animal" | "evidence" | "context" | "review";

type NodeAttributes = {
  label: string;
  x: number;
  y: number;
  size: number;
  color: string;
  kind: NodeKind;
  eyebrow: string;
  title: string;
  detail: string;
  source: string;
  eventId: string;
  time: string;
  duration: string;
  confidence: string;
  provenance: string;
  icon: "activity" | "animal" | "camera" | "clip" | "baseline" | "rule" | "shift" | "review";
  forceLabel?: boolean;
};

const nodePalette: Record<NodeKind, string> = {
  animal: "#8d949d",
  evidence: "#5f94ef",
  context: "#737a84",
  review: "#a3a9b2",
};

const graphNodes: Array<[string, NodeAttributes]> = [
  [
    "pacing",
    {
      label: "Pacing · 14 min",
      x: 0,
      y: 0,
      size: 22,
      color: nodePalette.evidence,
      kind: "evidence",
      eyebrow: "Behavior event",
      title: "Pacing · 14 min",
      detail: "Continuous pacing detected in Savannah Overlook.",
      source: "CAM 07 · Savannah Overlook",
      eventId: "EVT-2025-05-12-011542",
      time: "May 12, 2025 · 01:15:42",
      duration: "00:14:00",
      confidence: "Moderate · 0.62",
      provenance: "pacing > 10 min",
      icon: "activity",
      forceLabel: true,
    },
  ],
  [
    "rex",
    {
      label: "Rex",
      x: -3.1,
      y: 2.2,
      size: 15,
      color: nodePalette.animal,
      kind: "animal",
      eyebrow: "Animal",
      title: "Rex",
      detail: "Animal record associated with the selected evidence.",
      source: "ENC-07 animal registry",
      eventId: "ANM-REX-07",
      time: "Current record",
      duration: "—",
      confidence: "Verified identity",
      provenance: "Animal → Event",
      icon: "animal",
      forceLabel: true,
    },
  ],
  [
    "camera",
    {
      label: "CAM 07",
      x: 0,
      y: 3.1,
      size: 14,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Camera source",
      title: "CAM 07",
      detail: "North-facing enclosure camera covering Savannah Overlook.",
      source: "Savannah Overlook",
      eventId: "CAM-07",
      time: "23:00–05:00",
      duration: "06:00:00",
      confidence: "Coverage complete",
      provenance: "Camera → Clip → Event",
      icon: "camera",
      forceLabel: true,
    },
  ],
  [
    "clip",
    {
      label: "Clip · 01:15:42",
      x: 3.1,
      y: 2.2,
      size: 15,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Source clip",
      title: "Clip · 01:15:42",
      detail: "Source-aligned evidence window for the selected event.",
      source: "CAM 07 · Savannah Overlook",
      eventId: "CLIP-1842",
      time: "01:15:42",
      duration: "00:00:18",
      confidence: "Source evidence",
      provenance: "Clip → Event",
      icon: "clip",
      forceLabel: true,
    },
  ],
  [
    "baseline",
    {
      label: "Daytime baseline",
      x: 3.35,
      y: 0.35,
      size: 14,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Baseline context",
      title: "Daytime baseline",
      detail: "Prior daytime-only pacing baseline for Rex.",
      source: "Prior daytime shifts",
      eventId: "BASE-REX-PACING",
      time: "Rolling 14-day window",
      duration: "Mean · 4.5 min",
      confidence: "3.1σ delta",
      provenance: "Baseline → Event",
      icon: "baseline",
      forceLabel: true,
    },
  ],
  [
    "rule",
    {
      label: "Rule · pacing > 10 min",
      x: 2.45,
      y: -2,
      size: 14,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Deterministic rule",
      title: "pacing > 10 min",
      detail: "First matching deterministic rule for the observation.",
      source: "Rule set v1.3",
      eventId: "RULE-10.1",
      time: "Evaluated 01:29:42",
      duration: "—",
      confidence: "Deterministic",
      provenance: "Rule → Review item",
      icon: "rule",
      forceLabel: true,
    },
  ],
  [
    "severity",
    {
      label: "MODERATE",
      x: 0,
      y: -2.8,
      size: 14,
      color: nodePalette.evidence,
      kind: "evidence",
      eyebrow: "Rule severity",
      title: "MODERATE",
      detail: "Severity assigned by deterministic rule logic.",
      source: "Rule set v1.3",
      eventId: "SEV-1842",
      time: "01:29:42",
      duration: "—",
      confidence: "Deterministic",
      provenance: "pacing > 10 min",
      icon: "activity",
      forceLabel: true,
    },
  ],
  [
    "shift",
    {
      label: "Night shift",
      x: -2.55,
      y: -1.95,
      size: 14,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Shift",
      title: "Night shift",
      detail: "Configured monitoring window for May 12.",
      source: "Shift schedule",
      eventId: "SHIFT-2025-05-12",
      time: "23:00–05:00",
      duration: "06:00:00",
      confidence: "Configured",
      provenance: "Shift → Event",
      icon: "shift",
      forceLabel: true,
    },
  ],
  [
    "acknowledged",
    {
      label: "Acknowledged",
      x: -3.45,
      y: 0.25,
      size: 13,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Human review",
      title: "Acknowledged",
      detail: "Review recorded by the night supervisor.",
      source: "Maria Chen",
      eventId: "NOTE-512",
      time: "02:18:05",
      duration: "—",
      confidence: "Human outcome",
      provenance: "Review item → Outcome",
      icon: "review",
      forceLabel: true,
    },
  ],
];

const graphEdges: Array<[string, string]> = graphNodes
  .filter(([id]) => id !== "pacing")
  .map(([id]) => ["pacing", id]);

function NodeIcon({ icon }: { icon: NodeAttributes["icon"] }) {
  const props = { size: 17, strokeWidth: 1.7 };
  if (icon === "animal") return <CircleUserRound {...props} />;
  if (icon === "camera") return <Camera {...props} />;
  if (icon === "clip") return <Video {...props} />;
  if (icon === "baseline") return <BarChart3 {...props} />;
  if (icon === "rule") return <ShieldCheck {...props} />;
  if (icon === "shift") return <CalendarDays {...props} />;
  if (icon === "review") return <CheckCircle2 {...props} />;
  return <Activity {...props} />;
}

export default function WebGLGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<Sigma<NodeAttributes> | null>(null);
  const selectedRef = useRef("pacing");
  const hoveredRef = useRef<string | null>(null);
  const [selectedNode, setSelectedNode] = useState("pacing");

  useEffect(() => {
    if (!containerRef.current) return;

    const graph = new Graph<NodeAttributes>();
    graphNodes.forEach(([id, attributes]) => graph.addNode(id, attributes));
    graphEdges.forEach(([source, target], index) =>
      graph.addEdgeWithKey(`edge-${index}`, source, target, {
        color: "#5a616a",
        size: 1.2,
      }),
    );

    const renderer = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: false,
      labelFont: "Inter, Segoe UI, sans-serif",
      labelColor: { color: "#e8eaed" },
      labelSize: 12,
      labelWeight: "500",
      labelDensity: 1,
      labelGridCellSize: 74,
      labelRenderedSizeThreshold: 5,
      defaultEdgeColor: "#5a616a",
      defaultNodeColor: "#7c838c",
      defaultNodeType: "circle",
      hideEdgesOnMove: false,
      allowInvalidContainer: false,
      minCameraRatio: 0.55,
      maxCameraRatio: 2.2,
      nodeReducer: (node, attributes) => {
        const focus = hoveredRef.current ?? selectedRef.current;
        const connected = node === focus || graph.hasEdge(node, focus);

        if (focus && !connected) {
          return {
            ...attributes,
            color: "#333840",
            label: "",
            zIndex: 0,
          };
        }

        if (node === focus) {
          return {
            ...attributes,
            size: attributes.size * 1.14,
            color: "#2878f0",
            forceLabel: true,
            zIndex: 2,
          };
        }

        return {
          ...attributes,
          forceLabel: attributes.forceLabel || connected,
          zIndex: 1,
        };
      },
      edgeReducer: (edge, attributes) => {
        const focus = hoveredRef.current ?? selectedRef.current;
        const connected = graph.extremities(edge).includes(focus);
        return {
          ...attributes,
          color: connected ? "#2878f0" : "#555c65",
          size: connected ? 1.7 : 1,
          zIndex: connected ? 1 : 0,
        };
      },
    });

    renderer.on("clickNode", ({ node }) => {
      selectedRef.current = node;
      setSelectedNode(node);
      renderer.scheduleRefresh();
    });
    renderer.on("enterNode", ({ node }) => {
      hoveredRef.current = node;
      renderer.scheduleRefresh();
      containerRef.current?.classList.add("is-node-hovered");
    });
    renderer.on("leaveNode", () => {
      hoveredRef.current = null;
      renderer.scheduleRefresh();
      containerRef.current?.classList.remove("is-node-hovered");
    });
    renderer.on("clickStage", () => {
      selectedRef.current = "pacing";
      setSelectedNode("pacing");
      renderer.scheduleRefresh();
    });

    rendererRef.current = renderer;
    return () => {
      renderer.kill();
      rendererRef.current = null;
    };
  }, []);

  const selected =
    graphNodes.find(([id]) => id === selectedNode)?.[1] ?? graphNodes[0][1];

  return (
    <div className="node-stage-grid">
      <div className="node-canvas-frame">
        <div
          ref={containerRef}
          className="node-webgl-canvas"
          role="img"
          aria-label="Interactive evidence graph centered on a fourteen-minute pacing event"
        />
        <div className="node-zoom-controls">
          <button
            type="button"
            aria-label="Zoom in"
            onClick={() =>
              rendererRef.current?.getCamera().animatedZoom({ duration: 180 })
            }
          >
            <Plus size={15} />
          </button>
          <button
            type="button"
            aria-label="Zoom out"
            onClick={() =>
              rendererRef.current?.getCamera().animatedUnzoom({ duration: 180 })
            }
          >
            <Minus size={15} />
          </button>
          <button
            type="button"
            aria-label="Reset graph view"
            onClick={() =>
              rendererRef.current?.getCamera().animatedReset({ duration: 220 })
            }
          >
            <Focus size={15} />
          </button>
        </div>
        <div className="node-legend" aria-label="Graph legend">
          <span>
            <i className="blue-line" /> Evidence link
          </span>
          <span>
            <i className="gray-line" /> Context link
          </span>
          <span>
            <i className="blue-node" /> Selected node
          </span>
          <span>
            <i className="gray-node" /> Context node
          </span>
        </div>
      </div>

      <aside className="node-details-panel" aria-live="polite">
        <header>
          <strong>Node details</strong>
          <button type="button" aria-label="Close node details">
            <X size={15} />
          </button>
        </header>

        <div className="node-selected-heading">
          <span>
            <NodeIcon icon={selected.icon} />
          </span>
          <div>
            <strong>{selected.title}</strong>
            <small>Selected</small>
          </div>
          <button type="button" aria-label="Bookmark selected node">
            <Bookmark size={14} />
          </button>
          <button type="button" aria-label="More node actions">
            <MoreVertical size={14} />
          </button>
        </div>

        <dl className="node-detail-list">
          <div>
            <dt>Type</dt>
            <dd>{selected.eyebrow}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>{selected.source}</dd>
          </div>
          <div>
            <dt>Event ID</dt>
            <dd>{selected.eventId}</dd>
          </div>
          <div>
            <dt>Time</dt>
            <dd>{selected.time}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{selected.duration}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{selected.confidence}</dd>
          </div>
        </dl>

        <section className="node-rule-section">
          <span>Rule provenance</span>
          <strong>{selected.provenance}</strong>
          <small>v1.3 · deterministic first match</small>
        </section>

        <section className="node-review-section">
          <span>Review state</span>
          <strong>Acknowledged</strong>
          <small>Maria Chen · May 12, 2025 · 02:18:05</small>
        </section>

        <div className="node-detail-actions">
          <button type="button" className="primary-button">
            <Play size={14} />
            Open source clip
            <ExternalLink size={12} />
          </button>
          <button type="button" className="secondary-button">
            <Clock3 size={14} />
            View audit
            <ExternalLink size={12} />
          </button>
        </div>
      </aside>
    </div>
  );
}
