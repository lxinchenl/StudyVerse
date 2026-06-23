"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { ExplainerVideoPlayer } from "@/components/explainer/ExplainerVideoPlayer";
import { ExercisePanel } from "@/components/exercise/ExercisePanel";
import { MermaidBlock } from "@/components/mermaid/MermaidBlock";
import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer";
import { CodeLabPanel } from "@/lib/lazy-components";
import {
  fetchCodeLabSet,
  fetchExercises,
  fetchResource,
  RESOURCE_TYPE_LABELS
} from "@/lib/api";
import { rewriteNoteMarkdown } from "@/lib/constants";
import type { CodeLabSet, CourseResourceRef, ExerciseSet, GeneratedResource } from "@/lib/types";

function extractMermaidSource(content: string): string {
  const match = content.match(/```mermaid\s*([\s\S]*?)```/);
  return match?.[1]?.trim() ?? content.trim();
}

type LearningResourceModalProps = {
  open: boolean;
  resource: CourseResourceRef | null;
  userId: string;
  onClose: () => void;
};

export function LearningResourceModal({ open, resource, userId, onClose }: LearningResourceModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState<GeneratedResource | null>(null);
  const [exerciseSet, setExerciseSet] = useState<ExerciseSet | null>(null);
  const [labSet, setLabSet] = useState<CodeLabSet | null>(null);

  useEffect(() => {
    if (!open || !resource || !userId) return;

    let cancelled = false;
    setLoading(true);
    setError("");
    setMeta(null);
    setExerciseSet(null);
    setLabSet(null);

    async function load() {
      try {
        const res = await fetchResource(userId, resource!.resourceId);
        if (cancelled) return;
        setMeta(res);

        if (resource!.type === "exercise") {
          const questions = await fetchExercises(resource!.resourceId);
          if (cancelled) return;
          setExerciseSet({
            resourceId: resource!.resourceId,
            title: res.title,
            topic: res.topic,
            summary: res.summary,
            questions: questions.map((q) => ({
              id: q.id,
              topic: q.topic,
              difficulty: q.difficulty,
              question: q.question,
              gradingType: q.gradingType ?? "standard"
            }))
          });
        } else if (resource!.type === "code_lab") {
          const lab = await fetchCodeLabSet(userId, resource!.resourceId);
          if (cancelled) return;
          setLabSet(lab);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [open, resource, userId]);

  if (!open || !resource) return null;

  const typeLabel = RESOURCE_TYPE_LABELS[String(resource.type)] ?? String(resource.type);

  return (
    <div className="learning-resource-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="learning-resource-modal" onClick={(e) => e.stopPropagation()}>
        <header className="learning-resource-modal-head">
          <div>
            <span className={`learning-resource-type-badge learning-resource-type-badge--${resource.type}`}>
              {typeLabel}
            </span>
            <h3>{resource.title}</h3>
            {resource.learningOrderReason ? (
              <p className="muted learning-resource-modal-reason">{resource.learningOrderReason}</p>
            ) : null}
          </div>
          <button type="button" className="learning-resource-modal-close" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>

        <div className="learning-resource-modal-body">
          {loading ? (
            <p className="muted learning-resource-modal-loading">
              <Loader2 size={16} className="spin" /> 加载内容…
            </p>
          ) : error ? (
            <p className="learning-resource-modal-error">{error}</p>
          ) : meta?.playerUrl ? (
            <ExplainerVideoPlayer
              video={{
                resourceId: meta.id,
                title: meta.title,
                summary: meta.summary,
                playerUrl: meta.playerUrl,
                sceneCount: meta.sceneCount ?? 0
              }}
            />
          ) : resource.type === "mindmap" && meta ? (
            <MermaidBlock chart={extractMermaidSource(meta.content)} className="mindmap-canvas" />
          ) : resource.type === "exercise" && exerciseSet ? (
            <ExercisePanel exerciseSet={exerciseSet} userId={userId} embedded />
          ) : resource.type === "code_lab" && labSet ? (
            <CodeLabPanel labSet={labSet} userId={userId} compact />
          ) : meta ? (
            <MarkdownRenderer
              content={
                resource.type === "note" ? rewriteNoteMarkdown(meta.content, meta.id) : meta.content
              }
              variant={resource.type === "note" ? "note" : "default"}
            />
          ) : (
            <p className="muted">暂无内容</p>
          )}
        </div>
      </div>
    </div>
  );
}
