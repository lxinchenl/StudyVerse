"use client";

import { useCallback, useMemo, useState } from "react";
import type { Node, Relationship } from "@neo4j-nvl/base";

import { NvlGraphCanvas } from "./NvlGraphCanvas";
import type { GraphNode, KnowledgeGraphData } from "@/lib/types";

const NODE_COLORS: Record<string, string> = {
  Course: "#2563eb",
  Chapter: "#0891b2",
  KnowledgePoint: "#059669",
  Document: "#d97706",
  Exercise: "#dc2626",
};

function toNvlNodes(nodes: GraphNode[]): Node[] {
  const cols = Math.max(4, Math.ceil(Math.sqrt(nodes.length)));
  return nodes.map((node, i) => ({
    id: node.id,
    captions: [{ value: node.label }],
    color: NODE_COLORS[node.type] ?? "#64748b",
    size: node.type === "Course" ? 28 : 20,
    x: node.x ?? 80 + (i % cols) * 140,
    y: node.y ?? 80 + Math.floor(i / cols) * 110,
  }));
}

function toNvlRels(edges: KnowledgeGraphData["edges"]): Relationship[] {
  return edges.map((edge) => ({
    id: edge.id,
    from: edge.source,
    to: edge.target,
    captions: edge.relation ? [{ value: edge.relation }] : undefined,
    type: edge.relation,
  }));
}

export function KnowledgeGraphView({ data }: { data: KnowledgeGraphData }) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const nodeMap = useMemo(() => new Map(data.nodes.map((node) => [node.id, node])), [data.nodes]);
  const nvlNodes = useMemo(() => toNvlNodes(data.nodes), [data.nodes]);
  const nvlRels = useMemo(() => toNvlRels(data.edges), [data.edges]);

  const onNodeClick = useCallback(
    (node: Node) => {
      const found = nodeMap.get(node.id);
      if (found) setSelected(found);
    },
    [nodeMap],
  );

  const metaLine = data.meta
    ? `${data.meta.backend === "neo4j" ? "Neo4j 实时图谱" : "本地快照"} · ${data.meta.nodeCount} 节点 / ${data.meta.edgeCount} 关系`
    : `${data.nodes.length} 节点 / ${data.edges.length} 关系`;

  return (
    <div className="kg-layout">
      <div className="kg-canvas card">
        <div className="kg-canvas-body">
          {data.nodes.length === 0 ? (
            <p className="muted">暂无图谱数据。请确认 Neo4j 已连接，或存在本地 subgraphs.json 快照。</p>
          ) : (
            <NvlGraphCanvas nodes={nvlNodes} rels={nvlRels} onNodeClick={onNodeClick} />
          )}
        </div>
        <p className="muted kg-meta">
          {metaLine} · 滚轮缩放 · 拖动画布平移 · 可拖动节点
        </p>
      </div>
      <aside className="kg-sidebar card">
        <h3>节点详情</h3>
        {selected ? (
          <>
            <p>
              <strong>{selected.label}</strong>
            </p>
            <p className="muted">类型：{selected.type}</p>
            <p className="muted">ID：{selected.id}</p>
            <hr style={{ margin: "12px 0", border: "none", borderTop: "1px solid var(--border)" }} />
            <h4>关联关系</h4>
            {data.edges
              .filter((edge) => edge.source === selected.id || edge.target === selected.id)
              .map((edge) => (
                <p key={edge.id} className="muted" style={{ fontSize: 13 }}>
                  {edge.relation}: {nodeMap.get(edge.source === selected.id ? edge.target : edge.source)?.label}
                </p>
              ))}
          </>
        ) : (
          <p className="muted">点击节点查看详情</p>
        )}
        <hr style={{ margin: "16px 0", border: "none", borderTop: "1px solid var(--border)" }} />
        <div className="kg-legend">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <span key={type}>
              <i style={{ background: color }} /> {type}
            </span>
          ))}
        </div>
      </aside>
    </div>
  );
}
