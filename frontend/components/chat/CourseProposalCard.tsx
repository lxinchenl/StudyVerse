"use client";

import { useEffect, useMemo, useState } from "react";
import { BookOpen, Check, ChevronDown, ChevronUp, Clock, Plus, Trash2, X } from "lucide-react";

import type { CourseProposalCard as CourseProposalCardType, CourseProposalModule } from "@/lib/types";

type CourseProposalCardProps = {
  card: CourseProposalCardType;
  disabled?: boolean;
  onConfirm: (card: CourseProposalCardType) => void;
  onCancel: (card: CourseProposalCardType) => void;
};

function cloneCard(card: CourseProposalCardType): CourseProposalCardType {
  return {
    ...card,
    modules: card.modules.map((m) => ({ ...m, topics: [...m.topics] }))
  };
}

function defaultExpanded(card: CourseProposalCardType) {
  return card.status === "pending";
}

function defaultModuleExpanded(card: CourseProposalCardType) {
  return new Set(card.modules.map((_, index) => index));
}

function createNewModule(index: number): CourseProposalModule {
  return {
    id: `mod-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    title: `第 ${index + 1} 讲`,
    objective: "",
    chapterKey: "",
    estimatedMinutes: 45,
    topics: []
  };
}

export function CourseProposalCard({
  card,
  disabled = false,
  onConfirm,
  onCancel
}: CourseProposalCardProps) {
  const [draft, setDraft] = useState(() => cloneCard(card));
  const [expanded, setExpanded] = useState(() => defaultExpanded(card));
  const [expandedModules, setExpandedModules] = useState<Set<number>>(() => defaultModuleExpanded(card));
  const locked = disabled || card.status !== "pending";

  useEffect(() => {
    setDraft(cloneCard(card));
    setExpanded(defaultExpanded(card));
    setExpandedModules(defaultModuleExpanded(card));
  }, [card]);

  const totalMinutes = useMemo(
    () => draft.modules.reduce((sum, mod) => sum + (mod.estimatedMinutes || 0), 0),
    [draft.modules]
  );

  function updateModule(index: number, patch: Partial<CourseProposalModule>) {
    setDraft((prev) => ({
      ...prev,
      modules: prev.modules.map((mod, i) => (i === index ? { ...mod, ...patch } : mod))
    }));
  }

  function updateModuleTopics(index: number, value: string) {
    updateModule(index, {
      topics: value
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean)
    });
  }

  function toggleModule(index: number) {
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  function addModule(afterIndex?: number) {
    setDraft((prev) => {
      const insertAt = afterIndex === undefined ? prev.modules.length : afterIndex + 1;
      const nextModules = [...prev.modules];
      nextModules.splice(insertAt, 0, createNewModule(insertAt));
      return { ...prev, modules: nextModules };
    });
    setExpandedModules((prev) => {
      const insertAt = afterIndex === undefined ? draft.modules.length : afterIndex + 1;
      const next = new Set<number>();
      prev.forEach((i) => next.add(i >= insertAt ? i + 1 : i));
      next.add(insertAt);
      return next;
    });
  }

  function removeModule(index: number) {
    setDraft((prev) => {
      if (prev.modules.length <= 1) return prev;
      return {
        ...prev,
        modules: prev.modules.filter((_, i) => i !== index)
      };
    });
    setExpandedModules((prev) => {
      if (draft.modules.length <= 1) return prev;
      const next = new Set<number>();
      prev.forEach((i) => {
        if (i === index) return;
        next.add(i > index ? i - 1 : i);
      });
      return next;
    });
  }

  const statusLabel =
    card.status === "confirmed"
      ? "已确认"
      : card.status === "cancelled"
        ? "已取消"
        : "待确认";

  return (
    <div className={`course-proposal-card course-proposal-card--${card.status}`}>
      <button
        type="button"
        className="course-proposal-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="course-proposal-toggle-icon" aria-hidden>
          <BookOpen size={18} />
        </span>
        <span className="course-proposal-toggle-main">
          <span className="course-proposal-toggle-kicker">定制系统课大纲</span>
          <span className="course-proposal-toggle-title">{draft.courseTitle || "未命名课程"}</span>
          <span className="course-proposal-toggle-meta">
            <span>{draft.modules.length} 讲</span>
            <span aria-hidden>·</span>
            <span>
              <Clock size={12} />
              约 {totalMinutes} 分钟
            </span>
          </span>
        </span>
        <span className={`course-proposal-card-status course-proposal-card-status--${card.status}`}>
          {statusLabel}
        </span>
        <span className="course-proposal-toggle-chevron" aria-hidden>
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </button>

      {expanded ? (
        <div className="course-proposal-body">
          <section className="course-proposal-hero">
            <label className="course-proposal-field course-proposal-field--hero">
              <span className="course-proposal-field-label course-proposal-field-label--strong">课程名称</span>
              <input
                type="text"
                className="course-proposal-title-input"
                value={draft.courseTitle}
                disabled={locked}
                onChange={(e) => setDraft((prev) => ({ ...prev, courseTitle: e.target.value }))}
              />
            </label>
            <label className="course-proposal-field">
              <span className="course-proposal-field-label course-proposal-field-label--strong">课程简介</span>
              <textarea
                rows={2}
                className="course-proposal-summary-input"
                value={draft.summary}
                disabled={locked}
                onChange={(e) => setDraft((prev) => ({ ...prev, summary: e.target.value }))}
              />
            </label>
          </section>

          <section className="course-proposal-outline">
            <div className="course-proposal-outline-head">
              <h4>讲次大纲</h4>
              <p className="muted">可按讲次展开编辑，确认后按顺序自动生成资源</p>
              {!locked ? (
                <button type="button" className="btn-secondary course-proposal-add-btn" onClick={() => addModule()}>
                  <Plus size={14} />
                  新增一讲
                </button>
              ) : null}
            </div>

            <div className="course-proposal-modules">
              {draft.modules.map((mod, index) => {
                const moduleOpen = expandedModules.has(index);
                const step = String(index + 1).padStart(2, "0");
                return (
                  <article key={mod.id || index} className="course-proposal-module">
                    <button
                      type="button"
                      className="course-proposal-module-toggle"
                      onClick={() => toggleModule(index)}
                      aria-expanded={moduleOpen}
                    >
                      <span className="course-proposal-module-step">{step}</span>
                      <span className="course-proposal-module-head">
                        <span className="course-proposal-module-title">{mod.title || `第 ${index + 1} 讲`}</span>
                        <span className="course-proposal-module-chips">
                          <span className="course-proposal-chip">{mod.estimatedMinutes} 分钟</span>
                          {mod.chapterKey ? (
                            <span className="course-proposal-chip course-proposal-chip--muted">
                              {mod.chapterKey}
                            </span>
                          ) : null}
                        </span>
                      </span>
                      <span className="course-proposal-module-chevron" aria-hidden>
                        {moduleOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </span>
                    </button>

                    {moduleOpen ? (
                      <div className="course-proposal-module-body">
                        <label className="course-proposal-field">
                          <span>讲次标题</span>
                          <input
                            type="text"
                            value={mod.title}
                            disabled={locked}
                            onChange={(e) => updateModule(index, { title: e.target.value })}
                          />
                        </label>
                        <label className="course-proposal-field">
                          <span>学习目标</span>
                          <textarea
                            rows={2}
                            value={mod.objective}
                            disabled={locked}
                            onChange={(e) => updateModule(index, { objective: e.target.value })}
                          />
                        </label>
                        <div className="course-proposal-module-meta">
                          <label className="course-proposal-field course-proposal-field--inline">
                            <span>时长（分钟）</span>
                            <input
                              type="number"
                              min={20}
                              max={120}
                              value={mod.estimatedMinutes}
                              disabled={locked}
                              onChange={(e) =>
                                updateModule(index, { estimatedMinutes: Number(e.target.value) || 45 })
                              }
                            />
                          </label>
                          <label className="course-proposal-field course-proposal-field--inline">
                            <span>关联章节</span>
                            <input
                              type="text"
                              placeholder="如 ch6"
                              value={mod.chapterKey}
                              disabled={locked}
                              onChange={(e) => updateModule(index, { chapterKey: e.target.value })}
                            />
                          </label>
                        </div>
                        <label className="course-proposal-field">
                          <span>子主题（逗号分隔）</span>
                          <input
                            type="text"
                            value={mod.topics.join("，")}
                            disabled={locked}
                            onChange={(e) => updateModuleTopics(index, e.target.value)}
                          />
                        </label>
                        {mod.topics.length > 0 ? (
                          <div className="course-proposal-topic-tags">
                            {mod.topics.map((topic) => (
                              <span key={topic} className="course-proposal-topic-tag">
                                {topic}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {!locked ? (
                          <div className="course-proposal-module-actions">
                            <button
                              type="button"
                              className="btn-secondary course-proposal-inline-btn"
                              onClick={() => addModule(index)}
                            >
                              <Plus size={14} />
                              在下方新增一讲
                            </button>
                            <button
                              type="button"
                              className="btn-secondary course-proposal-inline-btn course-proposal-inline-btn--danger"
                              onClick={() => removeModule(index)}
                              disabled={draft.modules.length <= 1}
                              title={draft.modules.length <= 1 ? "至少保留一讲" : "删除本讲"}
                            >
                              <Trash2 size={14} />
                              删除本讲
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>

          {!locked ? (
            <div className="course-proposal-footer">
              <p className="muted course-proposal-hint">
                确认后将按讲次由编排 Agent 自主决定资源类型、数量与学习顺序，并同步到学习路径。
              </p>
              <div className="course-proposal-actions">
                <button type="button" className="btn-secondary" onClick={() => onCancel(draft)}>
                  <X size={14} />
                  取消
                </button>
                <button type="button" className="btn-primary" onClick={() => onConfirm(draft)}>
                  <Check size={14} />
                  同意并生成
                </button>
              </div>
            </div>
          ) : (
            <p className="muted course-proposal-hint course-proposal-hint--solo">
              {card.status === "confirmed"
                ? "已确认大纲，资源将按讲次顺序生成并写入学习路径。"
                : "已取消本次定制课生成。"}
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function proposalCardToApi(card: CourseProposalCardType) {
  return {
    course_title: card.courseTitle,
    summary: card.summary,
    topic: card.topic,
    modules: card.modules.map((mod) => ({
      id: mod.id,
      title: mod.title,
      objective: mod.objective,
      chapter_key: mod.chapterKey,
      estimated_minutes: mod.estimatedMinutes,
      topics: mod.topics
    }))
  };
}
