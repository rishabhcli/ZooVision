"use client";

import {
  ChevronDown,
  Filter,
  Info,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { GraphStage } from "./graph-stage";

export function GraphWorkspace() {
  return (
    <div className="page-stack graph-page">
      <div className="control-row graph-controls-row">
        <label className="select-control">
          <span>Enclosure</span>
          <select defaultValue="ENC-07 · Painted dogs">
            <option>ENC-01 · Elephants</option>
            <option>ENC-03 · Snow leopard</option>
            <option>ENC-05 · Otters</option>
            <option>ENC-07 · Painted dogs</option>
            <option>ENC-08 · Giraffes</option>
          </select>
          <ChevronDown size={14} />
        </label>
        <label className="select-control compact">
          <span>Animal</span>
          <select defaultValue="Rex">
            <option>Rex</option>
            <option>Zuri</option>
          </select>
          <ChevronDown size={14} />
        </label>
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
        <button className="icon-button bordered" type="button" aria-label="Graph settings">
          <SlidersHorizontal size={16} />
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
