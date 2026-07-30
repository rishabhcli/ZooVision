"use client";

import Graph from "graphology";
import {
  Check,
  ExternalLink,
  Focus,
  Minus,
  Plus,
  Video,
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
  forceLabel?: boolean;
};

const nodePalette: Record<NodeKind, string> = {
  animal: "#8da69b",
  evidence: "#a8aea9",
  context: "#777f83",
  review: "#c89b56",
};

const graphNodes: Array<[string, NodeAttributes]> = [
  [
    "rex",
    {
      label: "Rex · African painted dog",
      x: 0,
      y: 0,
      size: 18,
      color: nodePalette.animal,
      kind: "animal",
      eyebrow: "Animal",
      title: "Rex",
      detail: "African painted dog · ENC-07",
      source: "Animal record",
      forceLabel: true,
    },
  ],
  [
    "pacing",
    {
      label: "Pacing · 14 min",
      x: -2.7,
      y: 1.65,
      size: 13,
      color: nodePalette.review,
      kind: "review",
      eyebrow: "Observed behavior",
      title: "Pacing · 14 min",
      detail: "02:00–02:14 · confidence 0.91",
      source: "ENC-07 Camera 2",
      forceLabel: true,
    },
  ],
  [
    "water",
    {
      label: "Water contact · none since 20:30",
      x: 0,
      y: 2.75,
      size: 10,
      color: nodePalette.evidence,
      kind: "evidence",
      eyebrow: "Observed evidence",
      title: "Water contact",
      detail: "No contact observed since 20:30",
      source: "ENC-07 Camera 2",
      forceLabel: true,
    },
  ],
  [
    "baseline",
    {
      label: "Daytime baseline · 4.5 min",
      x: 2.9,
      y: 2.05,
      size: 11,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Daytime-only baseline",
      title: "Pacing baseline",
      detail: "Mean 4.5 min · 3.1σ delta",
      source: "Prior daytime shifts",
      forceLabel: true,
    },
  ],
  [
    "alert",
    {
      label: "MODERATE · review",
      x: 3.25,
      y: -0.3,
      size: 13,
      color: nodePalette.review,
      kind: "review",
      eyebrow: "Deterministic severity",
      title: "MODERATE",
      detail: "Rule fired: pacing > 10 min",
      source: "Rule engine",
      forceLabel: true,
    },
  ],
  [
    "clip",
    {
      label: "Clip · 02:06:40",
      x: 1.7,
      y: -2.3,
      size: 10,
      color: nodePalette.evidence,
      kind: "evidence",
      eyebrow: "Source clip",
      title: "Clip · 02:06:40",
      detail: "30-second evidence window",
      source: "ENC-07 Camera 2",
      forceLabel: true,
    },
  ],
  [
    "shift",
    {
      label: "Night shift · Jul 30",
      x: -0.6,
      y: -3,
      size: 9,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Shift",
      title: "Night shift",
      detail: "22:00–06:00 · July 30",
      source: "Shift record",
    },
  ],
  [
    "care",
    {
      label: "Care note · anxious at dusk",
      x: 3.8,
      y: -2.65,
      size: 9,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Keeper context",
      title: "Care note",
      detail: "Anxious at dusk",
      source: "Maria Chen · Jul 28",
    },
  ],
  [
    "observation",
    {
      label: "Observation · continuous motion",
      x: -4.05,
      y: 0,
      size: 8,
      color: nodePalette.evidence,
      kind: "evidence",
      eyebrow: "Normalized observation",
      title: "Continuous motion",
      detail: "Source-aligned behavior observation",
      source: "Validated segment output",
    },
  ],
  [
    "rule",
    {
      label: "Rule · pacing > 10 min",
      x: -3.45,
      y: -1.75,
      size: 9,
      color: nodePalette.review,
      kind: "review",
      eyebrow: "Rule provenance",
      title: "pacing > 10 min",
      detail: "First-match deterministic rule",
      source: "Rule set v1",
    },
  ],
  [
    "outcome",
    {
      label: "Outcome · pending",
      x: -2.05,
      y: -3.15,
      size: 8,
      color: nodePalette.context,
      kind: "context",
      eyebrow: "Human outcome",
      title: "Outcome pending",
      detail: "Awaiting keeper review",
      source: "Human review",
    },
  ],
];

const graphEdges: Array<[string, string]> = [
  ["rex", "pacing"],
  ["rex", "water"],
  ["rex", "baseline"],
  ["rex", "alert"],
  ["rex", "clip"],
  ["rex", "shift"],
  ["rex", "care"],
  ["pacing", "observation"],
  ["pacing", "rule"],
  ["pacing", "outcome"],
  ["pacing", "baseline"],
  ["pacing", "alert"],
  ["alert", "clip"],
];

export default function WebGLGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<Sigma<NodeAttributes> | null>(null);
  const graphRef = useRef<Graph<NodeAttributes> | null>(null);
  const selectedRef = useRef("pacing");
  const hoveredRef = useRef<string | null>(null);
  const [selectedNode, setSelectedNode] = useState("pacing");

  useEffect(() => {
    if (!containerRef.current) return;

    const graph = new Graph<NodeAttributes>();
    graphNodes.forEach(([id, attributes]) => graph.addNode(id, attributes));
    graphEdges.forEach(([source, target], index) =>
      graph.addEdgeWithKey(`edge-${index}`, source, target, {
        color: "#3f4848",
        size: 1.35,
      }),
    );

    const renderer = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: false,
      labelFont: "Segoe UI, sans-serif",
      labelColor: { color: "#d7dad6" },
      labelSize: 13,
      labelWeight: "500",
      labelDensity: 0.8,
      labelGridCellSize: 80,
      labelRenderedSizeThreshold: 7,
      defaultEdgeColor: "#3f4848",
      defaultNodeColor: "#8da69b",
      defaultNodeType: "circle",
      hideEdgesOnMove: false,
      allowInvalidContainer: false,
      enableEdgeEvents: true,
      minCameraRatio: 0.55,
      maxCameraRatio: 2.4,
      nodeReducer: (node, attributes) => {
        const selected = selectedRef.current;
        const hovered = hoveredRef.current;
        const focus = hovered ?? selected;
        const isNeighbor =
          focus && (node === focus || graph.hasEdge(node, focus));

        if (focus && !isNeighbor) {
          return {
            ...attributes,
            color: "#3f4545",
            label: "",
            zIndex: 0,
          };
        }

        if (node === focus) {
          return {
            ...attributes,
            size: attributes.size * 1.22,
            color: attributes.kind === "review" ? "#d0a15d" : "#a8b9b0",
            forceLabel: true,
            zIndex: 2,
          };
        }

        return {
          ...attributes,
          forceLabel: attributes.forceLabel || Boolean(isNeighbor),
          zIndex: 1,
        };
      },
      edgeReducer: (edge, attributes) => {
        const focus = hoveredRef.current ?? selectedRef.current;
        const extremities = graph.extremities(edge);
        const connected = focus && extremities.includes(focus);
        return {
          ...attributes,
          color: connected ? "#88918c" : "#303737",
          size: connected ? 2.2 : 1.05,
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
    graphRef.current = graph;

    return () => {
      renderer.kill();
      rendererRef.current = null;
      graphRef.current = null;
    };
  }, []);

  const selected =
    graphNodes.find(([id]) => id === selectedNode)?.[1] ?? graphNodes[0][1];

  return (
    <div className="webgl-graph-shell">
      <div
        ref={containerRef}
        className="webgl-graph"
        role="img"
        aria-label="Interactive evidence graph for Rex"
      />
      <div className="graph-canvas-badge">
        <span className="status-dot" />
        WebGL renderer
      </div>
      <div className="graph-zoom-controls">
        <button
          type="button"
          aria-label="Zoom out"
          onClick={() =>
            rendererRef.current?.getCamera().animatedUnzoom({
              duration: 220,
            })
          }
        >
          <Minus size={16} />
        </button>
        <button
          type="button"
          aria-label="Zoom in"
          onClick={() =>
            rendererRef.current?.getCamera().animatedZoom({
              duration: 220,
            })
          }
        >
          <Plus size={16} />
        </button>
        <button
          type="button"
          aria-label="Reset graph view"
          onClick={() =>
            rendererRef.current?.getCamera().animatedReset({
              duration: 280,
            })
          }
        >
          <Focus size={16} />
        </button>
      </div>
      <aside className="graph-inspector" aria-live="polite">
        <div className="inspector-head">
          <span
            className={`inspector-kind ${selected.kind}`}
            aria-hidden="true"
          />
          <div>
            <span className="section-kicker">{selected.eyebrow}</span>
            <h2>{selected.title}</h2>
          </div>
        </div>
        <p className="inspector-detail">{selected.detail}</p>
        <dl>
          <div>
            <dt>Source</dt>
            <dd>{selected.source}</dd>
          </div>
          <div>
            <dt>Event ID</dt>
            <dd>EVT-1842</dd>
          </div>
          <div>
            <dt>Review state</dt>
            <dd>
              <Check size={13} />
              Acknowledged
            </dd>
          </div>
        </dl>
        <div className="inspector-actions">
          <button className="primary-button" type="button">
            <Video size={15} />
            Open source clip
          </button>
          <button className="secondary-button" type="button">
            View audit
            <ExternalLink size={14} />
          </button>
        </div>
      </aside>
    </div>
  );
}
