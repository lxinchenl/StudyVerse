"use client";

import Link from "next/link";

import { MermaidBlock } from "@/components/mermaid/MermaidBlock";
import type { MindmapResource } from "@/lib/types";

export function MindmapViewer({
  mindmap,
  compact = false
}: {
  mindmap: MindmapResource;
  compact?: boolean;
}) {
  return (
    <div className={`mindmap-viewer${compact ? " mindmap-viewer-compact" : ""}`}>
      <div className="mindmap-viewer-head">
        <div>
          <strong>{mindmap.title}</strong>
          <p className="muted">{mindmap.summary}</p>
        </div>
        <Link href="/resources" className="btn-secondary">
          资源库
        </Link>
      </div>
      <MermaidBlock chart={mindmap.mermaidSource} className="mindmap-canvas" />
    </div>
  );
}
