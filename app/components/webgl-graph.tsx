"use client";

import type NVL from "@neo4j-nvl/base";
import type {
  Node as NvlNode,
  Relationship as NvlRelationship,
} from "@neo4j-nvl/base";
import { InteractiveNvlWrapper } from "@neo4j-nvl/react";
import {
  Activity,
  Camera,
  CircleUserRound,
  Database,
  Focus,
  Minus,
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
import {
  DEFAULT_WORKSPACE_PREFERENCES,
  listenForWorkspacePreferences,
  readWorkspacePreferences,
} from "../lib/workspace-preferences";

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

function nodePickerLabel(node: GraphNodeItem): string {
  return `${node.caption} · ${node.label} · ${node.id}`;
}

const propertyPriority = [
  "name",
  "species",
  "behavior",
  "activity_label",
  "evidence",
  "severity",
  "rule_fired",
  "rule_version",
  "camera_id",
  "enclosure_id",
  "source_path",
  "start_ts",
  "end_ts",
  "provider",
  "review_state",
];

function propertyRank(key: string): number {
  const rank = propertyPriority.indexOf(key);
  return rank === -1 ? propertyPriority.length : rank;
}

type GraphMode = "topology" | "clips" | "observations";

type GraphAssistantContext = {
  animalId: string | null;
  animalName: string | null;
  enclosureId: string | null;
  cameraId: string | null;
  sourcePath: string | null;
};

const topologyLabels = new Set([
  "Enclosure",
  "Animal",
  "Camera",
  "WelfareEvent",
  "DataGap",
]);

function graphPayloadForMode(payload: GraphPayload, mode: GraphMode): GraphPayload {
  if (mode !== "topology") return payload;
  const nodes = payload.nodes.filter((node) => topologyLabels.has(node.label));
  const visibleNodeIds = new Set(nodes.map((node) => node.id));
  const counts: Record<string, number> = {};
  for (const node of nodes) counts[node.label] = (counts[node.label] ?? 0) + 1;
  return {
    ...payload,
    nodes,
    relationships: payload.relationships.filter(
      (relationship) =>
        visibleNodeIds.has(relationship.from) && visibleNodeIds.has(relationship.to),
    ),
    counts,
  };
}

function nearbyGraphNodes(
  payload: GraphPayload,
  nodeId: string,
  maxDepth = 2,
): GraphNodeItem[] {
  const nodesById = new Map(payload.nodes.map((node) => [node.id, node]));
  let frontier = new Set([nodeId]);
  const visited = new Set(frontier);
  for (let depth = 0; depth < maxDepth; depth += 1) {
    const next = new Set<string>();
    for (const relationship of payload.relationships) {
      if (frontier.has(relationship.from) && !visited.has(relationship.to)) {
        next.add(relationship.to);
      }
      if (frontier.has(relationship.to) && !visited.has(relationship.from)) {
        next.add(relationship.from);
      }
    }
    next.forEach((id) => visited.add(id));
    frontier = next;
  }
  return [...visited]
    .map((id) => nodesById.get(id))
    .filter((node): node is GraphNodeItem => Boolean(node));
}

function uniqueNodeByProperty(
  nodes: GraphNodeItem[],
  label: string,
  property: string,
): GraphNodeItem | null {
  const matches = nodes.filter(
    (node) => node.label === label && node.properties[property],
  );
  const values = new Set(matches.map((node) => String(node.properties[property])));
  return values.size === 1 ? matches[0] : null;
}

function publishGraphAssistantContext(
  payload: GraphPayload,
  selectedNodeId: string | null,
) {
  let context: GraphAssistantContext = {
    animalId: null,
    animalName: null,
    enclosureId: null,
    cameraId: null,
    sourcePath: null,
  };
  if (selectedNodeId) {
    const selected = payload.nodes.find((node) => node.id === selectedNodeId) ?? null;
    const direct = nearbyGraphNodes(payload, selectedNodeId, 1);
    const nearby = nearbyGraphNodes(payload, selectedNodeId);
    const animal =
      (selected?.label === "Animal" ? selected : null) ??
      uniqueNodeByProperty(direct, "Animal", "animal_id") ??
      uniqueNodeByProperty(nearby, "Animal", "animal_id");
    const enclosure =
      (selected?.label === "Enclosure" ? selected : null) ??
      uniqueNodeByProperty(direct, "Enclosure", "enclosure_id") ??
      uniqueNodeByProperty(nearby, "Enclosure", "enclosure_id");
    const camera =
      (selected?.label === "Camera" ? selected : null) ??
      uniqueNodeByProperty(direct, "Camera", "camera_id") ??
      uniqueNodeByProperty(nearby, "Camera", "camera_id");
    const clip =
      (selected?.label === "Clip" ? selected : null) ??
      uniqueNodeByProperty(direct, "Clip", "source_path") ??
      uniqueNodeByProperty(nearby, "Clip", "source_path");
    context = {
      animalId: animal ? String(animal.properties.animal_id) : null,
      animalName: animal ? String(animal.properties.name ?? animal.caption) : null,
      enclosureId: enclosure ? String(enclosure.properties.enclosure_id) : null,
      cameraId: camera ? String(camera.properties.camera_id) : null,
      sourcePath: clip ? String(clip.properties.source_path) : null,
    };
  }
  window.sessionStorage.setItem(
    "zoovision:assistant-context",
    JSON.stringify(context),
  );
  window.dispatchEvent(
    new CustomEvent("zoovision:assistant-context", { detail: context }),
  );
}

function GraphCanvas({
  payload,
  mode,
  onChangeScope,
  onChangeMode,
}: {
  payload: GraphPayload;
  mode: GraphMode;
  onChangeScope: (scope: string | null) => void;
  onChangeMode: (mode: GraphMode) => void;
}) {
  const nvlRef = useRef<NVL | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(
    null,
  );
  const [nodeQuery, setNodeQuery] = useState("");
  const [compactGraphLabels, setCompactGraphLabels] = useState(
    DEFAULT_WORKSPACE_PREFERENCES.compactGraphLabels,
  );

  useEffect(() => {
    const storedPreferences = readWorkspacePreferences(window.localStorage);
    const hydrationFrame = window.requestAnimationFrame(() => {
      setCompactGraphLabels(storedPreferences.compactGraphLabels);
    });
    const stopListening = listenForWorkspacePreferences(window, (preferences) => {
      setCompactGraphLabels(preferences.compactGraphLabels);
    });
    return () => {
      window.cancelAnimationFrame(hydrationFrame);
      stopListening();
    };
  }, []);

  useEffect(() => {
    publishGraphAssistantContext(payload, null);
  }, [payload]);

  const selected = useMemo(
    () => payload.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [payload.nodes, selectedNodeId],
  );

  const selectedRelationship = useMemo(
    () =>
      payload.relationships.find(
        (relationship) => relationship.id === selectedRelationshipId,
      ) ?? null,
    [payload.relationships, selectedRelationshipId],
  );

  const relationshipEndpoints = useMemo(() => {
    if (!selectedRelationship) return null;
    return {
      from: payload.nodes.find((node) => node.id === selectedRelationship.from) ?? null,
      to: payload.nodes.find((node) => node.id === selectedRelationship.to) ?? null,
    };
  }, [payload.nodes, selectedRelationship]);

  const nodeChoices = useMemo(
    () =>
      payload.nodes.map((node) => ({
        id: node.id,
        label: nodePickerLabel(node),
      })),
    [payload.nodes],
  );

  const nvlNodes = useMemo<NvlNode[]>(
    () =>
      payload.nodes.map((node) => ({
        id: node.id,
        caption:
          compactGraphLabels && node.id !== selectedNodeId ? "" : node.caption,
        color: node.id === selectedNodeId ? "#c4df6c" : nodeColor(node),
        size:
          node.id === selectedNodeId ? Math.max(node.size * 1.35, 30) : node.size,
        selected: node.id === selectedNodeId,
        captionAlign: "bottom",
        captionSize: node.id === selectedNodeId ? 6 : 4,
        title: `${node.caption}\n${node.label}`,
      })),
    [compactGraphLabels, payload.nodes, selectedNodeId],
  );

  const nvlRelationships = useMemo<NvlRelationship[]>(
    () =>
      payload.relationships.map((relationship) => ({
        id: relationship.id,
        from: relationship.from,
        to: relationship.to,
        caption:
          compactGraphLabels && relationship.id !== selectedRelationshipId
            ? ""
            : relationship.caption,
        color:
          relationship.id === selectedRelationshipId ? "#c4df6c" : "#5a616a",
        selected: relationship.id === selectedRelationshipId,
        width: relationship.id === selectedRelationshipId ? 2.2 : 1.2,
      })),
    [compactGraphLabels, payload.relationships, selectedRelationshipId],
  );

  const fit = useCallback(() => {
    if (!nvlRef.current || payload.nodes.length === 0) return;
    nvlRef.current.fit(
      payload.nodes.map((node) => node.id),
      { animated: true },
    );
  }, [payload.nodes]);

  useEffect(() => {
    const timer = window.setTimeout(fit, 700);
    return () => window.clearTimeout(timer);
  }, [fit, payload.scope]);

  const detailProperties = selected
    ? Object.entries(selected.properties)
        .filter(([, value]) => value !== null)
        .sort(([left], [right]) => {
          const rankDifference = propertyRank(left) - propertyRank(right);
          return rankDifference || left.localeCompare(right);
        })
        .slice(0, 10)
    : [];

  return (
    <div className="node-stage-grid">
      <div className="node-canvas-frame">
        <div className="neo4j-graph-controls">
          <span>
            <i />
            Live Neo4j NVL
          </span>
          <div className="graph-mode-control" role="group" aria-label="Graph detail">
            <button
              type="button"
              aria-pressed={mode === "topology"}
              onClick={() => onChangeMode("topology")}
            >
              Topology
            </button>
            <button
              type="button"
              aria-pressed={mode === "clips"}
              onClick={() => onChangeMode("clips")}
            >
              Clips
            </button>
            <button
              type="button"
              aria-pressed={mode === "observations"}
              onClick={() => onChangeMode("observations")}
            >
              Observations
            </button>
          </div>
          <select
            aria-label="Filter graph by enclosure"
            value={payload.scope ?? ""}
            onChange={(event) => onChangeScope(event.target.value || null)}
          >
            <option value="">All enclosures</option>
            {payload.enclosures.map((enclosure) => (
              <option key={enclosure} value={enclosure}>
                {enclosure}
              </option>
            ))}
          </select>
          <input
            className="node-picker"
            type="search"
            list="graph-node-options"
            aria-label="Select a graph node to inspect"
            placeholder="Find a node"
            value={nodeQuery}
            onChange={(event) => {
              const query = event.target.value;
              const nodeId =
                nodeChoices.find((choice) => choice.label === query)?.id ?? null;
              setNodeQuery(query);
              setSelectedNodeId(nodeId);
              setSelectedRelationshipId(null);
              publishGraphAssistantContext(payload, nodeId);
              if (nodeId) {
                window.requestAnimationFrame(() => {
                  const graph = nvlRef.current;
                  if (!graph) return;
                  graph.fit([nodeId], { animated: true, maxZoom: 0.55 });
                });
              }
            }}
          />
          <datalist id="graph-node-options">
            {nodeChoices.map((choice) => (
              <option key={choice.id} value={choice.label} />
            ))}
          </datalist>
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
                  const payloadNode = payload.nodes.find(
                    (candidate) => candidate.id === node.id,
                  );
                  setNodeQuery(payloadNode ? nodePickerLabel(payloadNode) : "");
                  publishGraphAssistantContext(payload, node.id);
                },
                onRelationshipClick: (relationship: NvlRelationship) => {
                  setSelectedRelationshipId(relationship.id);
                  setSelectedNodeId(null);
                  setNodeQuery("");
                  publishGraphAssistantContext(payload, null);
                },
                onCanvasClick: () => {
                  setSelectedNodeId(null);
                  setSelectedRelationshipId(null);
                  setNodeQuery("");
                  publishGraphAssistantContext(payload, null);
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
            aria-label="Clear graph selection"
            disabled={!selectedNodeId && !selectedRelationshipId}
            onClick={() => {
              setSelectedNodeId(null);
              setSelectedRelationshipId(null);
              setNodeQuery("");
              publishGraphAssistantContext(payload, null);
            }}
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
        ) : selectedRelationship && relationshipEndpoints ? (
          <>
            <div className="node-selected-heading">
              <span>
                <Database size={17} strokeWidth={1.7} />
              </span>
              <div>
                <strong>{propertyLabel(selectedRelationship.caption)}</strong>
                <small>Relationship</small>
              </div>
            </div>
            <dl className="node-detail-list">
              <div>
                <dt>From</dt>
                <dd>
                  {relationshipEndpoints.from?.caption ?? selectedRelationship.from}
                </dd>
              </div>
              <div>
                <dt>To</dt>
                <dd>{relationshipEndpoints.to?.caption ?? selectedRelationship.to}</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{propertyLabel(selectedRelationship.caption)}</dd>
              </div>
            </dl>
            <section className="node-review-section">
              <span>Graph source</span>
              <strong>Neo4j video context graph</strong>
              <small>{selectedRelationship.id}</small>
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
  const [mode, setMode] = useState<GraphMode>("topology");
  const requestId = useRef(0);

  const load = useCallback((scope: string | null, nextMode: GraphMode) => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
    setError(null);
    setPayload(null);
    api
      .graph(scope, nextMode === "observations")
      .then((nextPayload) => {
        if (requestId.current === currentRequest) {
          setPayload(graphPayloadForMode(nextPayload, nextMode));
        }
      })
      .catch((caught: unknown) => {
        if (requestId.current !== currentRequest) return;
        setError(caught instanceof Error ? caught.message : "Unable to load Neo4j");
      });
  }, []);

  useEffect(() => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
    api
      .graph(null, false)
      .then((nextPayload) => {
        if (requestId.current === currentRequest) {
          setPayload(graphPayloadForMode(nextPayload, "topology"));
        }
      })
      .catch((caught: unknown) => {
        if (requestId.current !== currentRequest) return;
        setError(caught instanceof Error ? caught.message : "Unable to load Neo4j");
      });
  }, []);

  if (error) {
    return (
      <div className="graph-loading" role="alert">
        <p>{error}</p>
        <button
          type="button"
          className="secondary-button"
          onClick={() => load(null, mode)}
        >
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
  const graphKey = [
    payload.scope ?? "all",
    mode,
    payload.nodes.length,
    payload.relationships.length,
    payload.nodes[0]?.id ?? "empty",
    payload.nodes.at(-1)?.id ?? "empty",
  ].join(":");
  return (
    <GraphCanvas
      key={graphKey}
      payload={payload}
      mode={mode}
      onChangeScope={(scope) => load(scope, mode)}
      onChangeMode={(nextMode) => {
        if (nextMode === mode) return;
        setMode(nextMode);
        load(payload.scope, nextMode);
      }}
    />
  );
}
