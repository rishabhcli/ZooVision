"use client";

import dynamic from "next/dynamic";

const WebGLGraph = dynamic(() => import("./webgl-graph"), {
  ssr: false,
  loading: () => (
    <div className="graph-loading" role="status">
      <span />
      <p>Preparing WebGL graph…</p>
    </div>
  ),
});

export function GraphStage() {
  return <WebGLGraph />;
}
