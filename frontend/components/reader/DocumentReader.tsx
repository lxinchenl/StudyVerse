"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FileText, Highlighter, MessageCircle, StickyNote } from "lucide-react";

import { MarkdownRenderer } from "@/lib/lazy-components";
import { FilePreview, FilePreviewHint, resolvePreviewUrl, supportsFilePreview } from "@/components/reader/FilePreview";
import type { CourseDocument } from "@/lib/types";
import { DOC_TYPE_LABELS, fileDownloadUrl } from "@/lib/constants";
import { markDocumentProgress } from "@/lib/api";

type ViewMode = "preview" | "text";

export function DocumentReader({ document, userId }: { document: CourseDocument; userId: string }) {
  const [selectedText, setSelectedText] = useState("");
  const [note, setNote] = useState("");
  const [progress, setProgress] = useState(document.progress);
  const [viewMode, setViewMode] = useState<ViewMode>(
    supportsFilePreview(document.type) ? "preview" : "text"
  );
  const maxPptPageReported = useRef(0);
  const downloadUrl = fileDownloadUrl(document.fileUrl);
  const previewUrl = resolvePreviewUrl(document);
  const canPreview = supportsFilePreview(document.type) && !!previewUrl;

  useEffect(() => {
    setProgress(document.progress);
    maxPptPageReported.current = 0;
  }, [document.id, document.progress]);

  function handleMouseUp() {
    const text = window.getSelection()?.toString().trim() ?? "";
    if (text) setSelectedText(text);
  }

  const pushProgress = useCallback(
    async (payload: { viewedPage?: number; totalPages?: number; completed?: boolean }) => {
      try {
        const result = await markDocumentProgress(userId, document.id, payload);
        setProgress(result.documentProgress);
      } catch {
        // ignore non-blocking progress updates
      }
    },
    [document.id, userId]
  );

  useEffect(() => {
    if (!userId) return;
    if (document.type === "pdf" || document.type === "docx") {
      void pushProgress({
        completed: true,
        totalPages: document.pages
      });
    }
  }, [document.type, document.pages, pushProgress, userId]);

  const handlePptPageChange = useCallback(
    (page: number, totalPages: number) => {
      if (document.type !== "pptx") return;
      const safePage = Math.max(1, Math.floor(page));
      if (safePage <= maxPptPageReported.current) return;
      maxPptPageReported.current = safePage;
      void pushProgress({
        viewedPage: safePage,
        totalPages: totalPages || document.pages || undefined
      });
    },
    [document.pages, document.type, pushProgress]
  );

  return (
    <div className="reader-layout">
      <aside className="reader-sidebar">
        <div className="panel-card">
          <h3>文档信息</h3>
          <p><strong>类型：</strong>{DOC_TYPE_LABELS[document.type] ?? document.type}</p>
          {document.fileName ? <p><strong>文件名：</strong>{document.fileName}</p> : null}
          {document.pages ? <p><strong>页数：</strong>{document.pages}</p> : null}
          <p><strong>阅读进度：</strong>{Math.round(progress)}%</p>
          {downloadUrl ? (
            <a href={downloadUrl} className="btn-secondary" style={{ display: "inline-flex", marginTop: 12 }} download={document.fileName}>
              <Download size={16} /> 下载原文件
            </a>
          ) : null}
        </div>
        {canPreview ? (
          <div className="panel-card">
            <h3>阅读模式</h3>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button
                type="button"
                className={viewMode === "preview" ? "btn-primary" : "btn-secondary"}
                onClick={() => setViewMode("preview")}
              >
                原版预览
              </button>
              <button
                type="button"
                className={viewMode === "text" ? "btn-primary" : "btn-secondary"}
                onClick={() => setViewMode("text")}
              >
                纯文本
              </button>
            </div>
          </div>
        ) : null}
        {selectedText ? (
          <div className="panel-card highlight-card">
            <h3><Highlighter size={16} /> 选中文本</h3>
            <p className="selected-text">{selectedText}</p>
            <button className="btn-primary" type="button">
              <MessageCircle size={16} /> 向 Agent 提问
            </button>
          </div>
        ) : null}
        <div className="panel-card">
          <h3><StickyNote size={16} /> 笔记</h3>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="记录你的理解或疑问..."
            rows={4}
          />
        </div>
      </aside>
      <article className="reader-content" onMouseUp={handleMouseUp}>
        {canPreview && viewMode === "preview" ? (
          <div className="file-preview-shell">
            <FilePreviewHint type={document.type} />
            <FilePreview document={document} url={previewUrl!} onPptPageChange={handlePptPageChange} />
          </div>
        ) : canPreview && viewMode === "text" ? (
          <div className="file-placeholder">
            <FileText size={48} />
            <h3>{document.title}</h3>
            <p className="muted">从课件提取的纯文本，便于搜索与 Agent 引用。</p>
            {document.content ? <MarkdownRenderer content={document.content} /> : null}
          </div>
        ) : (
          <MarkdownRenderer content={document.content ?? "暂无内容"} />
        )}
      </article>
    </div>
  );
}
