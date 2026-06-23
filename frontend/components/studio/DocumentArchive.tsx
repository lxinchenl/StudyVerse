"use client";

import Link from "next/link";
import { memo, useCallback, useEffect, useState } from "react";
import { BookOpen, Loader2, Trash2, X } from "lucide-react";

import { ExplainerVideoPlayer } from "@/components/explainer/ExplainerVideoPlayer";
import { CodeLabPanel, MarkdownRenderer, MindmapViewer } from "@/lib/lazy-components";
import { deleteResource, fetchCodeLabSet, RESOURCE_TYPE_LABELS } from "@/lib/api";
import { rewriteNoteMarkdown } from "@/lib/constants";
import type { CodeLabSet, GeneratedResource, ResourceType } from "@/lib/types";

function extractMermaidSource(content: string): string {
  const match = content.match(/```mermaid\s*([\s\S]*?)```/);
  return match?.[1]?.trim() ?? content.trim();
}

const TYPE_ORDER: ResourceType[] = ["video_script", "mindmap", "exercise", "note", "code_lab"];

interface DocumentArchiveProps {
  open: boolean;
  onClose: () => void;
  resources: GeneratedResource[];
  userId: string;
  onResourceDeleted: (resourceId: string) => void;
}

function CodeLabArchiveBody({ resourceId, userId }: { resourceId: string; userId: string }) {
  const [labSet, setLabSet] = useState<CodeLabSet | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchCodeLabSet(userId, resourceId)
      .then((data) => {
        if (!cancelled) setLabSet(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [resourceId, userId]);

  if (loading) {
    return (
      <p className="muted">
        <Loader2 size={14} className="spin" /> 加载编程题…
      </p>
    );
  }
  if (error) return <p className="muted" style={{ color: "var(--danger)" }}>{error}</p>;
  if (!labSet) return <p className="muted">未找到题目数据</p>;
  return <CodeLabPanel labSet={labSet} userId={userId} />;
}

function ArchiveViewer({
  res,
  userId,
  onBack,
  onDelete,
  deleting,
}: {
  res: GeneratedResource;
  userId: string;
  onBack: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <div className="archive-viewer">
      <div className="archive-viewer-toolbar">
        <button type="button" className="archive-back" onClick={onBack}>
          ← 返回书架
        </button>
        <button
          type="button"
          className="archive-delete-btn"
          onClick={onDelete}
          disabled={deleting}
          aria-label="删除资源"
        >
          {deleting ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
          删除
        </button>
      </div>
      <div className="archive-viewer-head">
        <span className="tag">{RESOURCE_TYPE_LABELS[res.type]}</span>
        <h3>{res.title}</h3>
        {res.topic ? <p className="muted">主题：{res.topic}</p> : null}
        <p className="muted">{res.summary}</p>
      </div>
      <div className="archive-viewer-body">
        {res.playerUrl ? (
          <ExplainerVideoPlayer
            video={{
              resourceId: res.id,
              title: res.title,
              summary: res.summary,
              playerUrl: res.playerUrl,
              sceneCount: res.sceneCount ?? 0,
            }}
          />
        ) : res.type === "mindmap" ? (
          <MindmapViewer
            mindmap={{
              resourceId: res.id,
              title: res.title,
              topic: res.topic,
              summary: res.summary,
              mermaidSource: extractMermaidSource(res.content),
            }}
          />
        ) : res.type === "exercise" ? (
          <p className="muted">
            题目已同步到练习页，请前往
            <Link href={`/practice?resource=${encodeURIComponent(res.id)}`}> 练习与测评 </Link>
          </p>
        ) : res.type === "code_lab" ? (
          <CodeLabArchiveBody resourceId={res.id} userId={userId} />
        ) : (
          <MarkdownRenderer
            content={
              res.type === "note"
                ? rewriteNoteMarkdown(res.content, res.id)
                : res.content
            }
            variant={res.type === "note" ? "note" : "default"}
          />
        )}
      </div>
    </div>
  );
}

function DocumentArchiveInner({
  open,
  onClose,
  resources,
  userId,
  onResourceDeleted,
}: DocumentArchiveProps) {
  const [selected, setSelected] = useState<GeneratedResource | null>(null);
  const [filter, setFilter] = useState<ResourceType | "all">("all");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      setSelected(null);
      setFilter("all");
      setError("");
    }
  }, [open]);

  const handleDelete = useCallback(
    async (res: GeneratedResource) => {
      if (deletingId) return;
      if (!window.confirm(`确定删除「${res.title}」？此操作不可恢复。`)) return;
      setError("");
      setDeletingId(res.id);
      try {
        await deleteResource(userId, res.id);
        onResourceDeleted(res.id);
        if (selected?.id === res.id) setSelected(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "删除失败");
      } finally {
        setDeletingId(null);
      }
    },
    [deletingId, onResourceDeleted, selected?.id, userId],
  );

  if (!open) return null;

  const filtered =
    filter === "all" ? resources : resources.filter((r) => r.type === filter);

  return (
    <div className="archive-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="archive-panel" role="dialog" aria-label="文档库">
        <header className="archive-header">
          <div>
            <BookOpen size={20} />
            <h2>文档库</h2>
            <span className="muted">共 {resources.length} 份资料</span>
          </div>
          <button type="button" className="studio-close-btn" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>

        {error ? <p className="archive-error">{error}</p> : null}

        {selected ? (
          <ArchiveViewer
            res={selected}
            userId={userId}
            onBack={() => setSelected(null)}
            onDelete={() => handleDelete(selected)}
            deleting={deletingId === selected.id}
          />
        ) : (
          <>
            <div className="archive-filters">
              <button
                type="button"
                className={filter === "all" ? "active" : ""}
                onClick={() => setFilter("all")}
              >
                全部
              </button>
              {TYPE_ORDER.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={filter === t ? "active" : ""}
                  onClick={() => setFilter(t)}
                >
                  {RESOURCE_TYPE_LABELS[t]}
                </button>
              ))}
            </div>
            <div className="archive-shelf-grid">
              {filtered.length === 0 ? (
                <p className="archive-empty">书架空空，派 Agent 生成第一份资料吧</p>
              ) : (
                filtered.map((res) => (
                  <div key={res.id} className="archive-book-wrap">
                    <button type="button" className="archive-book" onClick={() => setSelected(res)}>
                      <div className="archive-book-spine" />
                      <div className="archive-book-cover">
                        <span className="archive-book-type">{RESOURCE_TYPE_LABELS[res.type]}</span>
                        <strong>{res.title}</strong>
                        <span className="muted">{res.createdAt}</span>
                      </div>
                    </button>
                    <button
                      type="button"
                      className="archive-book-delete"
                      aria-label={`删除 ${res.title}`}
                      disabled={deletingId === res.id}
                      onClick={() => handleDelete(res)}
                    >
                      {deletingId === res.id ? (
                        <Loader2 size={14} className="spin" />
                      ) : (
                        <Trash2 size={14} />
                      )}
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export const DocumentArchive = memo(DocumentArchiveInner);
