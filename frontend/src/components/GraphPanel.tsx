import type { Node as NvlNode, Relationship as NvlRelationship } from "@neo4j-nvl/base";
import type NVL from "@neo4j-nvl/base";
import { InteractiveNvlWrapper } from "@neo4j-nvl/react";
import { Focus, Layers, Maximize2, Network, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SEVERITY_COLOR } from "../severity";
import type { GraphNodeItem, GraphPayload } from "../types";

/** One colour per node label, drawn from the console's existing palette. */
const LABEL_COLOR: Record<string, string> = {
  Enclosure: "#183f33",
  Animal: "#285747",
  WelfareEvent: "#a02717",
  Observation: "#2b6cb0",
  Camera: "#68716d",
  DataGap: "#bf8410"
};

function nodeColor(node: GraphNodeItem) {
  if (node.label === "WelfareEvent" && node.severity) {
    return SEVERITY_COLOR[node.severity] ?? LABEL_COLOR.WelfareEvent;
  }
  return LABEL_COLOR[node.label] ?? "#68716d";
}

export function GraphPanel({
  graph,
  scope,
  onScope,
  onOpenEvent
}: {
  graph: GraphPayload | null;
  scope: string | null;
  onScope: (enclosureId: string | null) => void;
  onOpenEvent: (eventId: string) => void;
}) {
  const [selected, setSelected] = useState<GraphNodeItem | null>(null);
  const [hiddenLabels, setHiddenLabels] = useState<Set<string>>(new Set());
  const nvlRef = useRef<NVL | null>(null);

  const fit = useCallback(() => {
    const instance = nvlRef.current;
    if (!instance) return;
    instance.fit(
      instance.getNodes().map((node) => node.id),
      { animated: true }
    );
  }, []);

  const visibleNodes = useMemo(
    () => (graph?.nodes ?? []).filter((node) => !hiddenLabels.has(node.label)),
    [graph, hiddenLabels]
  );

  const nvlNodes = useMemo<NvlNode[]>(
    () =>
      visibleNodes.map((node) => ({
        id: node.id,
        caption: node.caption,
        color: nodeColor(node),
        size: node.size,
        captionAlign: "bottom",
        captionSize: 2,
        selected: selected?.id === node.id
      })),
    [visibleNodes, selected]
  );

  const nvlRels = useMemo<NvlRelationship[]>(() => {
    const present = new Set(visibleNodes.map((node) => node.id));
    return (graph?.relationships ?? [])
      .filter((rel) => present.has(rel.from) && present.has(rel.to))
      .map((rel) => ({
        id: rel.id,
        from: rel.from,
        to: rel.to,
        caption: rel.caption,
        color: "#c3c8c0",
        width: 1.4
      }));
  }, [graph, visibleNodes]);

  const byId = useMemo(() => {
    const map = new Map<string, GraphNodeItem>();
    (graph?.nodes ?? []).forEach((node) => map.set(node.id, node));
    return map;
  }, [graph]);

  const handleNodeClick = useCallback(
    (node: NvlNode) => setSelected(byId.get(node.id) ?? null),
    [byId]
  );

  const toggleLabel = useCallback((label: string) => {
    setHiddenLabels((current) => {
      const next = new Set(current);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(fit, 900);
    return () => window.clearTimeout(timer);
  }, [scope, graph, fit]);

  /** Neighbours of the selected node, so one click opens into the rest. */
  const neighbours = useMemo(() => {
    if (!selected || !graph) return [];
    return graph.relationships
      .filter((rel) => rel.from === selected.id || rel.to === selected.id)
      .map((rel) => {
        const otherId = rel.from === selected.id ? rel.to : rel.from;
        return { relationship: rel.caption, node: byId.get(otherId) };
      })
      .filter((item): item is { relationship: string; node: GraphNodeItem } =>
        Boolean(item.node)
      );
  }, [selected, graph, byId]);

  return (
    <div className="graph-panel">
      <div className="graph-toolbar">
        <div className="enclosure-switch" role="tablist" aria-label="Enclosure web">
          <button
            role="tab"
            aria-selected={scope === null}
            className={scope === null ? "web-chip active" : "web-chip"}
            onClick={() => onScope(null)}
          >
            <Network size={14} /> All enclosures
          </button>
          {(graph?.enclosures ?? []).map((enclosure) => (
            <button
              key={enclosure}
              role="tab"
              aria-selected={scope === enclosure}
              className={scope === enclosure ? "web-chip active" : "web-chip"}
              onClick={() => onScope(enclosure)}
            >
              {enclosure}
            </button>
          ))}
        </div>
        <div className="label-filters">
          <button className="label-chip" onClick={fit} title="Fit graph to view">
            <Maximize2 size={13} /> Fit
          </button>
          <Layers size={14} />
          {Object.keys(LABEL_COLOR).map((label) => {
            const count = graph?.counts?.[label] ?? 0;
            if (!count) return null;
            const hidden = hiddenLabels.has(label);
            return (
              <button
                key={label}
                className={hidden ? "label-chip off" : "label-chip"}
                onClick={() => toggleLabel(label)}
                title={`${hidden ? "Show" : "Hide"} ${label} nodes`}
              >
                <span style={{ background: LABEL_COLOR[label] }} />
                {label}
                <em>{count}</em>
              </button>
            );
          })}
        </div>
      </div>

      <div className="graph-canvas">
        {nvlNodes.length === 0 ? (
          <div className="graph-empty">
            <Network size={26} />
            <p>No graph nodes in this scope.</p>
          </div>
        ) : (
          <InteractiveNvlWrapper
            ref={nvlRef}
            nodes={nvlNodes}
            rels={nvlRels}
            nvlOptions={{
              layout: "forceDirected",
              initialZoom: 0.8,
              renderer: "canvas",
              relationshipThreshold: 0.2
            }}
            mouseEventCallbacks={{
              onNodeClick: handleNodeClick,
              onCanvasClick: () => setSelected(null),
              onZoom: true,
              onPan: true,
              onDrag: true
            }}
            style={{ width: "100%", height: "100%" }}
          />
        )}

        {selected && (
          <aside className="node-inspector">
            <header>
              <span
                className="inspector-label"
                style={{ background: nodeColor(selected) }}
              >
                {selected.label}
              </span>
              <button
                className="icon-button"
                aria-label="Close inspector"
                onClick={() => setSelected(null)}
              >
                <X size={16} />
              </button>
            </header>
            <h3>{selected.caption}</h3>
            <dl>
              {Object.entries(selected.properties)
                .filter(([, value]) => value !== null && value !== "")
                .map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
            </dl>
            {selected.label === "WelfareEvent" && (
              <button
                className="primary-button"
                onClick={() => onOpenEvent(String(selected.properties.event_id))}
              >
                <Focus size={15} /> Open evidence
              </button>
            )}
            {neighbours.length > 0 && (
              <div className="neighbour-list">
                <span className="eyebrow">Connected</span>
                {neighbours.slice(0, 12).map(({ relationship, node }) => (
                  <button key={node.id} onClick={() => setSelected(node)}>
                    <span
                      className="flag-dot"
                      style={{ background: nodeColor(node) }}
                    />
                    <strong>{node.caption}</strong>
                    <small>{relationship}</small>
                  </button>
                ))}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

export default GraphPanel;
