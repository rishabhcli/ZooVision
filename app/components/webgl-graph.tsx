"use client";

import type NVL from "@neo4j-nvl/base";
import type {
  Node as NvlNode,
  Relationship as NvlRelationship,
} from "@neo4j-nvl/base";
import { InteractiveNvlWrapper } from "@neo4j-nvl/react";
import {
  Activity,
  Bookmark,
  Camera,
  CircleUserRound,
  Database,
  Focus,
  Minus,
  MoreVertical,
  Plus,
  ShieldCheck,
  Video,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  api,
  type GraphNodeItem,
  type GraphPayload,
} from "../lib/api";

const labelColors: Record<string, string> = {
  Animal: "#a3a9b2",
  Camera: "#2db39e",
  Clip: "#23a7d8",
  DataGap: "#e05e6f",
  Enclosure: "#72a46b",
  Observation: "#7b83ce",
  WelfareEvent: "#5f94ef",
};

const severityColors: Record<string, string> = {
  CRITICAL: "#e05e6f",
  HIGH: "#e7a94b",
  MODERATE: "#5f94ef",
  LOW: "#2db39e",
};

function nodeColor(node: GraphNodeItem): string {
  return (
    (node.severity && severityColors[node.severity]) ||
    labelColors[node.label] ||
    "#737a84"
  );
}

function NodeIcon({ label }: { label: string }) {
  const props = { size: 17, strokeWidth: 1.7 };
  if (label === "Animal") return <CircleUserRound {...props} />;
  if (label === "Camera") return <Camera {...props} />;
  if (label === "Clip") return <Video {...props} />;
  if (label === "WelfareEvent") return <ShieldCheck {...props} />;
  if (label === "Observation") return <Activity {...props} />;
  return <Database {...props} />;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (Array.isArray(value)) return value.map(displayValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function propertyLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function GraphCanvas({
  payload,
  onRefresh,
}: {
  payload: GraphPayload;
  onRefresh: (scope: string | null) => void;
}) {
  const nvlRef = useRef<NVL | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(
    null,
  );

  const selected = useMemo(
    () => payload.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [payload.nodes, selectedNodeId],
  );

  const nvlNodes = useMemo<NvlNode[]>(
    () =>
      payload.nodes.map((node) => ({
        id: node.id,
        caption: node.caption,
        color: nodeColor(node),
        size: node.size,
        selected: node.id === selectedNodeId,
        captionAlign: "bottom",
        captionSize: 3,
        title: `${node.caption}\n${node.label}`,
      })),
    [payload.nodes, selectedNodeId],
  );

  const nvlRelationships = useMemo<NvlRelationship[]>(
    () =>
      payload.relationships.map((relationship) => ({
        id: relationship.id,
        from: relationship.from,
        to: relationship.to,
        caption: relationship.caption,
        color:
          relationship.id === selectedRelationshipId ? "#2878f0" : "#5a616a",
        selected: relationship.id === selectedRelationshipId,
        width: relationship.id === selectedRelationshipId ? 2.2 : 1.2,
      })),
    [payload.relationships, selectedRelationshipId],
  );

  const fit = useCallback(() => {
    if (!nvlRef.current || nvlNodes.length === 0) return;
    nvlRef.current.fit(
      nvlNodes.map((node) => node.id),
      { animated: true },
    );
  }, [nvlNodes]);

  useEffect(() => {
    const timer = window.setTimeout(fit, 700);
    return () => window.clearTimeout(timer);
  }, [fit, payload.scope]);

  const detailProperties = selected
    ? Object.entries(selected.properties).filter(([, value]) => value !== null).slice(0, 9)
    : [];

  return (
    <div className="node-stage-grid">
      <div className="node-canvas-frame">
        <div className="neo4j-graph-controls">
          <span>
            <i />
            Live Neo4j NVL
          </span>
          <select
            aria-label="Filter graph by enclosure"
            value={payload.scope ?? ""}
            onChange={(event) => onRefresh(event.target.value || null)}
          >
            <option value="">All enclosures</option>
            {payload.enclosures.map((enclosure) => (
              <option key={enclosure} value={enclosure}>
                {enclosure}
              </option>
            ))}
          </select>
        </div>

        {nvlNodes.length === 0 ? (
          <div className="graph-loading" role="status">
            <p>No Neo4j nodes in this enclosure.</p>
          </div>
        ) : (
          <div
            className="node-webgl-canvas"
            role="img"
            aria-label={`Interactive Neo4j video context graph with ${payload.nodes.length} nodes`}
          >
            <InteractiveNvlWrapper
              ref={nvlRef}
              nodes={nvlNodes}
              rels={nvlRelationships}
              nvlOptions={{
                layout: "d3Force",
                initialZoom: 0.8,
                minZoom: 0.1,
                maxZoom: 5,
                relationshipThickness: 2,
                disableTelemetry: true,
              }}
              mouseEventCallbacks={{
                onNodeClick: (node: NvlNode) => {
                  setSelectedNodeId(node.id);
                  setSelectedRelationshipId(null);
                },
                onRelationshipClick: (relationship: NvlRelationship) => {
                  setSelectedRelationshipId(relationship.id);
                  setSelectedNodeId(null);
                },
                onCanvasClick: () => {
                  setSelectedNodeId(null);
                  setSelectedRelationshipId(null);
                },
                onZoom: true,
                onPan: true,
                onDrag: true,
              }}
              style={{ width: "100%", height: "100%" }}
            />
          </div>
        )}

        <div className="node-zoom-controls">
          <button
            type="button"
            aria-label="Zoom in"
            onClick={() => {
              const graph = nvlRef.current;
              if (graph) graph.setZoom(Math.min(graph.getScale() * 1.2, 5));
            }}
          >
            <Plus size={15} />
          </button>
          <button
            type="button"
            aria-label="Zoom out"
            onClick={() => {
              const graph = nvlRef.current;
              if (graph) graph.setZoom(Math.max(graph.getScale() / 1.2, 0.1));
            }}
          >
            <Minus size={15} />
          </button>
          <button type="button" aria-label="Fit graph to view" onClick={fit}>
            <Focus size={15} />
          </button>
        </div>

        <div className="node-legend" aria-label="Graph legend">
          {Object.entries(payload.counts)
            .filter(([, count]) => count > 0)
            .map(([label, count]) => (
              <span key={label}>
                <i style={{ background: labelColors[label] ?? "#737a84" }} />
                {label} {count}
              </span>
            ))}
        </div>
      </div>

      <aside className="node-details-panel" aria-live="polite">
        <header>
          <strong>Node details</strong>
          <button
            type="button"
            aria-label="Clear selected node"
            onClick={() => setSelectedNodeId(null)}
          >
            <X size={15} />
          </button>
        </header>
        {selected ? (
          <>
            <div className="node-selected-heading">
              <span>
                <NodeIcon label={selected.label} />
              </span>
              <div>
                <strong>{selected.caption}</strong>
                <small>{selected.label}</small>
              </div>
              <button type="button" aria-label="Bookmark selected node">
                <Bookmark size={14} />
              </button>
              <button type="button" aria-label="More node actions">
                <MoreVertical size={14} />
              </button>
            </div>
            <dl className="node-detail-list">
              {detailProperties.map(([key, value]) => (
                <div key={key}>
                  <dt>{propertyLabel(key)}</dt>
                  <dd>{displayValue(value)}</dd>
                </div>
              ))}
            </dl>
            {selected.properties.rule_fired ? (
              <section className="node-rule-section">
                <span>Deterministic rule provenance</span>
                <strong>{displayValue(selected.properties.rule_fired)}</strong>
                <small>
                  {displayValue(selected.properties.rule_version)} · first match
                </small>
              </section>
            ) : null}
            <section className="node-review-section">
              <span>Graph source</span>
              <strong>Neo4j video context graph</strong>
              <small>{selected.id}</small>
            </section>
          </>
        ) : (
          <div className="graph-loading" role="status">
            <p>No node selected.</p>
          </div>
        )}
      </aside>
    </div>
  );
}

export default function WebGLGraph() {
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((scope: string | null = null) => {
    setError(null);
    api
      .graph(scope)
      .then(setPayload)
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "Unable to load Neo4j"),
      );
  }, []);

  useEffect(() => {
    api
      .graph()
      .then(setPayload)
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "Unable to load Neo4j"),
      );
  }, []);

  if (error) {
    return (
      <div className="graph-loading" role="alert">
        <p>{error}</p>
        <button type="button" className="secondary-button" onClick={() => load()}>
          Retry graph connection
        </button>
      </div>
    );
  }
  if (!payload) {
    return (
      <div className="graph-loading" role="status">
        <span />
        <p>Reading Neo4j video context graph…</p>
      </div>
    );
  }
  return (
    <GraphCanvas
      key={`${payload.scope ?? "all"}:${payload.nodes.map((node) => node.id).join(",")}`}
      payload={payload}
      onRefresh={load}
    />
  );
}
