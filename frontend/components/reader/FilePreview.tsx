"use client";

import { PptxViewer } from "@pagus-kit/react";
import { useEffect, useRef, useState } from "react";
import { renderAsync } from "docx-preview";

import type { CourseDocument } from "@/lib/types";
import { DOC_TYPE_LABELS, fileDownloadUrl } from "@/lib/constants";

type PreviewType = "pdf" | "pptx" | "docx";

const PREVIEW_TYPES = new Set<string>(["pdf", "pptx", "docx"]);

export function supportsFilePreview(type: string): type is PreviewType {
  return PREVIEW_TYPES.has(type);
}

export function FilePreview({
  document,
  url,
  onPptPageChange
}: {
  document: CourseDocument;
  url: string;
  onPptPageChange?: (page: number, totalPages: number) => void;
}) {
  const docxRef = useRef<HTMLDivElement>(null);
  const [pptxData, setPptxData] = useState<ArrayBuffer | null>(null);
  const [pptxSlideCount, setPptxSlideCount] = useState(0);
  const [loading, setLoading] = useState(document.type !== "pdf");
  const [error, setError] = useState("");

  useEffect(() => {
    if (document.type === "pdf") {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    setPptxData(null);
    setPptxSlideCount(0);

    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error(`加载失败 (${response.status})`);
        return response.arrayBuffer();
      })
      .then(async (buffer) => {
        if (cancelled) return;
        if (document.type === "pptx") {
          setPptxData(buffer);
          setLoading(false);
          return;
        }
        if (document.type === "docx") {
          const container = docxRef.current;
          if (!container) {
            throw new Error("预览容器未就绪");
          }
          container.innerHTML = "";
          await renderAsync(buffer, container, undefined, {
            className: "docx-preview-root",
            inWrapper: true,
            breakPages: true
          });
          if (!cancelled) setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "预览失败");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [url, document.type]);

  if (document.type === "pdf") {
    return (
      <iframe
        src={url}
        title={document.title}
        className="file-preview-pdf"
      />
    );
  }

  if (document.type === "docx") {
    return (
      <div className="file-preview-docx-wrap">
        {loading ? <p className="muted">正在加载预览...</p> : null}
        {error ? <p className="muted preview-error">{error}</p> : null}
        <div
          ref={docxRef}
          className="file-preview-docx"
          style={{ display: loading || error ? "none" : "block" }}
        />
      </div>
    );
  }

  if (loading) {
    return <p className="muted">正在加载预览...</p>;
  }

  if (error) {
    return <p className="muted preview-error">{error}</p>;
  }

  if (document.type === "pptx" && pptxData) {
    return (
      <div className="file-preview-pptx">
        <PptxViewer
          file={pptxData}
          onLoad={(info) => {
            setPptxSlideCount(info.slideCount);
            if (info.slideCount > 0) {
              onPptPageChange?.(1, info.slideCount);
            }
          }}
          onPageChange={(page) => {
            const totalPages = pptxSlideCount || document.pages || 0;
            onPptPageChange?.(page, totalPages);
          }}
          onError={(err) => setError(err.message)}
        />
      </div>
    );
  }

  return null;
}

export function FilePreviewHint({ type }: { type: string }) {
  return (
    <p className="muted preview-hint">
      {DOC_TYPE_LABELS[type] ?? type} 在浏览器内渲染（PDF 原生 / Word docx-preview / PPT SVG），
      复杂动画或特殊字体可能与 Office 略有差异，可下载原文件对照。
    </p>
  );
}

export function resolvePreviewUrl(document: CourseDocument): string | null {
  return fileDownloadUrl(document.fileUrl);
}
