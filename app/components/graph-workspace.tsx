"use client";

import { Filter, Info, MapPin, Search } from "lucide-react";
import { GraphStage } from "./graph-stage";

export function GraphWorkspace() {
  return (
    <div className="page-stack graph-page">
      <div className="control-row graph-controls-row">
        <div className="graph-context-readout">
          <MapPin size={15} />
          <span>
            <small>ENC-07 · North habitat</small>
            <strong>Rex · current night shift</strong>
          </span>
        </div>
        <label className="search-control">
          <Search size={16} />
          <input
            type="search"
            placeholder="Find evidence, behavior, or event"
            aria-label="Search graph"
          />
        </label>
        <button className="quiet-button" type="button">
          <Filter size={15} />
          Filters
        </button>
      </div>

      <section className="graph-workspace">
        <div className="graph-heading">
          <div>
            <span className="section-kicker">Connected evidence</span>
            <h1>Rex · July 30 night shift</h1>
          </div>
          <div className="graph-legend">
            <span>
              <i className="legend-dot animal" />
              Animal
            </span>
            <span>
              <i className="legend-dot evidence" />
              Evidence
            </span>
            <span>
              <i className="legend-dot context" />
              Context
            </span>
            <span>
              <i className="legend-dot review" />
              Review
            </span>
          </div>
        </div>
        <div className="graph-notice">
          <Info size={15} />
          Select a node to inspect its source and rule provenance. Drag to pan;
          scroll to zoom.
        </div>
        <GraphStage />
      </section>
    </div>
  );
}
