"use client";

import Link from "next/link";

import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer";
import { rewriteNoteMarkdown } from "@/lib/constants";
import type { NoteResource } from "@/lib/types";

export function NoteViewer({
  note,
  compact = false
}: {
  note: NoteResource;
  compact?: boolean;
}) {
  const markdown = rewriteNoteMarkdown(note.markdown, note.resourceId);

  return (
    <div className={`note-viewer${compact ? " note-viewer-compact" : ""}`}>
      <div className="note-viewer-head">
        <div>
          <strong>{note.title}</strong>
          <p className="muted">{note.summary}</p>
        </div>
        <Link href="/resources" className="btn-secondary">
          资源库
        </Link>
      </div>
      <div className="note-viewer-body">
        <MarkdownRenderer content={markdown} variant="note" />
      </div>
    </div>
  );
}
