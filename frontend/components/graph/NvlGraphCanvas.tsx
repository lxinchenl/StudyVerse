"use client";

import { useMemo, useRef } from "react";
import type { Node, Relationship } from "@neo4j-nvl/base";
import NVL from "@neo4j-nvl/base";
import { InteractiveNvlWrapper } from "@neo4j-nvl/react";

export function NvlGraphCanvas({
  nodes,
  rels,
  onNodeClick,
}: {
  nodes: Node[];
  rels: Relationship[];
  onNodeClick: (node: Node) => void;
}) {
  const nvlRef = useRef<NVL>(null);

  const nvlOptions = useMemo(
    () => ({
      disableTelemetry: true,
      // SharedWorker 在 Next/Turbopack 下常加载失败，导致布局中断、节点堆叠、交互未绑定
      disableWebWorkers: true,
      renderer: "canvas" as const,
    }),
    [],
  );

  const nvlCallbacks = useMemo(
    () => ({
      onInitialization: () => {
        nvlRef.current?.fit([], { animated: false });
      },
      onLayoutDone: () => {
        nvlRef.current?.fit([], { animated: false });
      },
    }),
    [],
  );

  const mouseEventCallbacks = useMemo(
    () => ({
      onNodeClick,
      onPan: true,
      onZoom: true,
      onZoomAndPan: true,
      onDrag: true,
      onDragStart: true,
      onDragEnd: true,
    }),
    [onNodeClick],
  );

  return (
    <InteractiveNvlWrapper
      ref={nvlRef}
      className="kg-nvl-canvas"
      nodes={nodes}
      rels={rels}
      layout="d3Force"
      nvlOptions={nvlOptions}
      nvlCallbacks={nvlCallbacks}
      mouseEventCallbacks={mouseEventCallbacks}
    />
  );
}
