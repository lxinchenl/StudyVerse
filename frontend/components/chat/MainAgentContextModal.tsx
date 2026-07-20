"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Loader2, RefreshCw, X } from "lucide-react";

import type { MainAgentContext } from "@/lib/types";

type MainAgentContextModalProps = {
  open: boolean;
  loading: boolean;
  context: MainAgentContext | null;
  onClose: () => void;
  onRefresh: () => void;
};

function Section({
  title,
  children
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="main-context-section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}

export function MainAgentContextModal({
  open,
  loading,
  context,
  onClose,
  onRefresh
}: MainAgentContextModalProps) {
  const bodyRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!open || !context || !bodyRef.current) return;
    bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [open, context?.updatedAt, context?.step, context?.promptText]);

  if (!open) return null;

  return (
    <div className="main-context-overlay" onClick={onClose} role="presentation">
      <div
        className="main-context-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="main-context-title"
      >
        <header className="main-context-head">
          <div>
            <p className="main-context-kicker">Main Agent Context</p>
            <h3 id="main-context-title">主 Agent 完整上下文</h3>
            <p className="main-context-meta">
              {context
                ? `ReAct 第 ${context.step} 步 · 更新于 ${context.updatedAt || "—"}`
                : "等待推理上下文…"}
              {loading ? " · 推理进行中，内容实时刷新" : ""}
            </p>
          </div>
          <div className="main-context-head-actions">
            <button type="button" className="btn-secondary main-context-action" onClick={onRefresh}>
              <RefreshCw size={14} />
              刷新
            </button>
            <button
              type="button"
              className="main-context-close"
              onClick={onClose}
              aria-label="关闭"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="main-context-body">
          {!context ? (
            <div className="main-context-empty">
              <Loader2 size={18} className="main-context-spinner" />
              <span>暂无上下文，发送消息后将在此实时显示。</span>
            </div>
          ) : (
            <>
              <Section title="资料状态">
                <p className="main-context-summary">{context.materialSummary}</p>
                {context.retrieval.mergeBoundary ? (
                  <p className="main-context-note">
                    分桶：检索 {context.retrieval.mergeBoundary.search_chunks ?? 0} 条 / 文档阅读{" "}
                    {context.retrieval.mergeBoundary.document_chunks ?? 0} 条
                  </p>
                ) : null}
                {context.retrieval.summarized ? (
                  <p className="main-context-note">
                    已自动摘要（触发 {context.retrieval.summarized.trigger_chars ?? 0} 字 → 目标{" "}
                    {context.retrieval.summarized.target_chars ?? 5000} 字）
                  </p>
                ) : null}
              </Section>

              {context.retrieval.chunks.length ? (
                <Section title="已加载资料">
                  <div className="main-context-chunks">
                    {context.retrieval.chunks.map((chunk) => (
                      <article key={`${chunk.chunkId ?? chunk.index}-${chunk.title}`} className="main-context-chunk">
                        <header>
                          <strong>
                            【资料{chunk.index}】{chunk.title || "未命名"}
                          </strong>
                          <span>
                            {chunk.sourceType || "unknown"}
                            {chunk.score != null ? ` · score ${chunk.score}` : ""}
                          </span>
                        </header>
                        <pre>{chunk.text}</pre>
                      </article>
                    ))}
                  </div>
                </Section>
              ) : null}

              <Section title="System Prompt（人设 + ReAct 规则）">
                <pre className="main-context-prompt main-context-prompt-system">
                  {context.systemText || "（暂无；推理开始后会显示完整 system）"}
                </pre>
              </Section>

              <Section title="User Prompt（画像 + 会话 + 资料摘要）">
                <pre ref={bodyRef} className="main-context-prompt">
                  {context.userPromptText || context.promptText}
                </pre>
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
