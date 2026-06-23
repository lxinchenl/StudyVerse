"use client";

import dynamic from "next/dynamic";

const chunkLoading = (label: string) => (
  <p className="muted" style={{ fontSize: 13, margin: "8px 0" }}>
    {label}
  </p>
);

export const MarkdownRenderer = dynamic(
  () => import("@/components/markdown/MarkdownRenderer").then((mod) => mod.MarkdownRenderer),
  { loading: () => chunkLoading("加载内容渲染器…") },
);

export const MindmapViewer = dynamic(
  () => import("@/components/mindmap/MindmapViewer").then((mod) => mod.MindmapViewer),
  { loading: () => chunkLoading("加载思维导图…") },
);

export const NoteViewer = dynamic(
  () => import("@/components/note/NoteViewer").then((mod) => mod.NoteViewer),
  { loading: () => chunkLoading("加载笔记…") },
);

export const CodeLabPanel = dynamic(
  () => import("@/components/code-lab/CodeLabPanel").then((mod) => mod.CodeLabPanel),
  { loading: () => chunkLoading("加载编程练习…") },
);

export const ExercisePanel = dynamic(
  () => import("@/components/exercise/ExercisePanel").then((mod) => mod.ExercisePanel),
  { loading: () => chunkLoading("加载练习题…") },
);
