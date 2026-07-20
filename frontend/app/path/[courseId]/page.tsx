"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Clock,
  ListChecks,
  Sparkles
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { LearningResourceModal } from "@/components/path/LearningResourceModal";
import { useAuth } from "@/lib/auth";
import { fetchLearningCourseDetail, RESOURCE_TYPE_LABELS } from "@/lib/api";
import type { CourseResourceRef, LearningCourseDetail, LearningModule } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  pending: "待开始",
  in_progress: "进行中",
  done: "已完成"
};

const RESOURCE_VISUAL_META: Record<string, { key: string; subtitle: string }> = {
  note: { key: "note", subtitle: "NOTES" },
  mindmap: { key: "mindmap", subtitle: "MINDMAP" },
  video_script: { key: "video", subtitle: "VIDEO" },
  exercise: { key: "exercises", subtitle: "EXERCISES" },
  code_lab: { key: "exercises", subtitle: "EXERCISES" }
};

function stripModuleTitle(title: string): string {
  return title.replace(/^第\s*\d+\s*讲[：:\s]*/u, "").trim() || title;
}

function clampTilt(delta: number, threshold = 20): number {
  if (delta >= 0) return Math.min(delta, threshold);
  return Math.max(delta, -threshold);
}

function handleCardMouseEnter(e: MouseEvent<HTMLButtonElement>) {
  const card = e.currentTarget;
  card.style.setProperty("--overlay-left", "-42px");
  card.style.setProperty("--overlay-top", "-58px");
  card.style.setProperty("--overlay-scale", "1.05");
  card.style.setProperty("--overlay-overflow", "visible");
  card.style.setProperty("--brand-logo-width", "88px");
  card.style.setProperty("--card-stack", "1");
  card.style.setProperty("--card-shell-scale", "1.1");
}

function handleCardMouseMove(e: MouseEvent<HTMLButtonElement>) {
  const card = e.currentTarget;
  const rect = card.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const dx = e.clientX - centerX;
  const dy = e.clientY - centerY;
  const rx = clampTilt(dx);
  const ry = clampTilt(dy);
  const brightness = 1 - (ry / 20) * 0.05;

  card.style.setProperty("--card-rotate-y", `${rx}deg`);
  card.style.setProperty("--card-rotate-x", `${-ry / 1.5}deg`);
  card.style.setProperty("--card-brightness", `${brightness}`);
  card.style.setProperty("--card-shadow-x", `${-rx}px`);
  card.style.setProperty("--card-shadow-y", `${-ry}px`);
  card.style.setProperty("--poster-move-x", `${dx / 8}px`);
  card.style.setProperty("--poster-move-y", `${dy / 13}px`);
  card.style.setProperty("--overlay-move-x", `${dx / 10}px`);
  card.style.setProperty("--overlay-move-y", `${dy / 15}px`);
  card.style.setProperty(
    "--overlay-filter",
    `drop-shadow(${-rx / 7}px ${-ry / 7}px 0 white)`
  );
}

function handleCardMouseLeave(e: MouseEvent<HTMLButtonElement>) {
  const card = e.currentTarget;
  card.style.setProperty("--card-rotate-y", "0deg");
  card.style.setProperty("--card-rotate-x", "0deg");
  card.style.setProperty("--card-brightness", "1");
  card.style.setProperty("--card-shadow-x", "0px");
  card.style.setProperty("--card-shadow-y", "0px");
  card.style.setProperty("--poster-move-x", "0px");
  card.style.setProperty("--poster-move-y", "0px");
  card.style.setProperty("--overlay-move-x", "0px");
  card.style.setProperty("--overlay-move-y", "0px");
  card.style.setProperty("--overlay-filter", "none");
  card.style.setProperty("--overlay-left", "0px");
  card.style.setProperty("--overlay-top", "0px");
  card.style.setProperty("--overlay-scale", "1");
  card.style.setProperty("--overlay-overflow", "hidden");
  card.style.setProperty("--brand-logo-width", "72px");
  card.style.setProperty("--card-stack", "0");
  card.style.setProperty("--card-shell-scale", "1");
}

function LearningModuleSection({
  module,
  index,
  onOpenResource,
  expanded,
  onToggle
}: {
  module: LearningModule;
  index: number;
  onOpenResource: (resource: CourseResourceRef) => void;
  expanded: boolean;
  onToggle: () => void;
}) {
  const resources = useMemo(
    () => [...module.resources].sort((a, b) => a.order - b.order),
    [module.resources]
  );
  const displayTitle = stripModuleTitle(module.title);

  return (
    <section
      className={`learning-module-section learning-module-section--${module.status} ${
        expanded ? "is-expanded" : "is-collapsed"
      }`}
    >
      <span className={`learning-module-timeline-dot learning-module-timeline-dot--${module.status}`} aria-hidden />
      <button type="button" className="learning-module-toggle" onClick={onToggle}>
        <div className="learning-module-section-head">
          <div className="learning-module-index">{String(index + 1).padStart(2, "0")}</div>
          <div className="learning-module-head-main">
            <div className="learning-module-head-row">
              <h3>{displayTitle}</h3>
              <span className={`learning-module-status learning-module-status--${module.status}`}>
                {STATUS_LABELS[module.status] ?? module.status}
              </span>
            </div>
            <p className="learning-module-objective">{module.objective}</p>
            <div className="learning-module-meta-row">
              <span>
                <Clock size={14} /> 预计 {module.estimatedMinutes} 分钟
              </span>
              {module.chapterKey ? <span>章节 {module.chapterKey}</span> : null}
              <span>{resources.length} 项资源</span>
            </div>
            <div className="learning-module-progress-pill">
              <ListChecks size={13} />
              <span>学习清单第 {index + 1} 讲</span>
            </div>
          </div>
        </div>
        <span className={`learning-module-toggle-icon ${expanded ? "open" : ""}`} aria-hidden>
          <ChevronDown size={18} />
        </span>
      </button>

      {!expanded ? (
        <p className="learning-module-collapsed-hint">点击上方标题展开本讲学习内容</p>
      ) : resources.length > 0 ? (
        <div className="learning-module-track-wrap">
          <p className="learning-module-track-label">
            <Sparkles size={14} /> 按学习顺序展开
          </p>
          <div className="learning-module-track">
            {resources.map((res, resIndex) => {
              const typeLabel = RESOURCE_TYPE_LABELS[String(res.type)] ?? String(res.type);
              const visual = RESOURCE_VISUAL_META[String(res.type)] ?? { key: "note", subtitle: "RESOURCE" };
              return (
                <div key={`${module.id}-${res.resourceId}`} className="learning-module-track-item">
                  {resIndex > 0 ? (
                    <span className="learning-module-track-arrow" aria-hidden>
                      <ChevronRight size={18} />
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className={`learning-resource-card learning-resource-card--${res.type}`}
                    onClick={() => onOpenResource(res)}
                    onMouseEnter={handleCardMouseEnter}
                    onMouseMove={handleCardMouseMove}
                    onMouseLeave={handleCardMouseLeave}
                  >
                    <span className="learning-resource-card-order">{res.order}</span>
                    <div className="learning-resource-card-poster" aria-hidden>
                      <span className="learning-resource-card-dots" />
                      <span className="learning-resource-card-overlay-area">
                        <span className="learning-resource-card-overlay-img">
                          <span className="learning-resource-card-brand-logo">
                            <img src={`/card/${visual.key}.png`} alt="" />
                          </span>
                        </span>
                      </span>
                      <span className={`learning-resource-card-badge learning-resource-card-badge--${res.type}`}>
                        {typeLabel}
                      </span>
                      <span
                        className={`learning-resource-card-badge-shadow learning-resource-card-badge-shadow--${res.type}`}
                      />
                      <span className="learning-resource-card-mascot">
                        <img src={`/card/character_${visual.key}.png`} alt="" />
                      </span>
                    </div>
                    <div className="learning-resource-card-bottom">
                      <strong className="learning-resource-card-title">{res.title}</strong>
                      <span className="learning-resource-card-type">{visual.subtitle}</span>
                    </div>
                    {res.learningOrderReason ? (
                      <p className="learning-resource-card-reason">{res.learningOrderReason}</p>
                    ) : null}
                    <span className="learning-resource-card-action">点击查看</span>
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <p className="muted learning-module-empty">本讲资源尚未生成完成</p>
      )}
    </section>
  );
}

export default function LearningCoursePage() {
  const params = useParams();
  const courseId = String(params.courseId ?? "");
  const { user } = useAuth();
  const [course, setCourse] = useState<LearningCourseDetail | null>(null);
  const [error, setError] = useState("");
  const [activeResource, setActiveResource] = useState<CourseResourceRef | null>(null);
  const [expandedModuleIds, setExpandedModuleIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!user || !courseId) return;
    fetchLearningCourseDetail(user.id, courseId)
      .then(setCourse)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user, courseId]);

  useEffect(() => {
    if (!course) return;
    const inProgress = course.modules.find((m) => m.status === "in_progress");
    const fallback = course.modules[0];
    const initial = inProgress?.id ?? fallback?.id;
    setExpandedModuleIds(initial ? new Set([initial]) : new Set());
  }, [course?.id]);

  const doneCount = course?.modules.filter((m) => m.status === "done").length ?? 0;
  const moduleCount = course?.modules.length ?? 0;
  const totalMinutes = course?.modules.reduce((sum, mod) => sum + (mod.estimatedMinutes || 0), 0) ?? 0;
  const totalResources =
    course?.modules.reduce((sum, mod) => sum + (mod.resources?.length || 0), 0) ?? 0;
  const progressPct = moduleCount ? Math.round((doneCount / moduleCount) * 100) : 0;

  const toggleModule = (moduleId: string) => {
    setExpandedModuleIds((prev) => {
      const next = new Set(prev);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  };

  const expandAll = () => {
    if (!course) return;
    setExpandedModuleIds(new Set(course.modules.map((m) => m.id)));
  };

  const collapseAll = () => {
    setExpandedModuleIds(new Set());
  };

  return (
    <AppShell title={course?.title ?? "定制课"} subtitle="按讲次顺序学习，点击资源卡片即可在弹窗中查看">
      <div className="learning-course-page">
        <Link href="/path" className="btn-secondary learning-course-back">
          <ArrowLeft size={16} /> 返回学习路径
        </Link>

        {error ? <p className="muted">{error}</p> : null}

        {!course ? (
          <p className="muted">加载中…</p>
        ) : (
          <>
            <header className="learning-course-hero">
              <div className="learning-course-hero-text">
                <p className="learning-course-hero-kicker">定制系统课</p>
                <h2>{course.title}</h2>
                <p className="learning-course-hero-summary">{course.summary || course.topic}</p>
                <div className="learning-course-hero-tags">
                  <span className="learning-course-tag">{course.topic}</span>
                  <span className="learning-course-tag learning-course-tag--status">
                    状态：{STATUS_LABELS[course.status] ?? course.status}
                  </span>
                  <span className="learning-course-tag learning-course-tag--date">
                    <CalendarDays size={14} />
                    创建于 {course.createdAt || "未知"}
                  </span>
                </div>
              </div>
              <div className="learning-course-hero-stats">
                <div className="learning-course-stat">
                  <span className="learning-course-stat-value">{moduleCount}</span>
                  <span className="learning-course-stat-label">讲次</span>
                </div>
                <div className="learning-course-stat">
                  <span className="learning-course-stat-value">{progressPct}%</span>
                  <span className="learning-course-stat-label">进度</span>
                </div>
                <div className="learning-course-stat-grid">
                  <div className="learning-course-stat-card">
                    <span className="learning-course-stat-card-value">{totalResources}</span>
                    <span className="learning-course-stat-card-label">资源总数</span>
                  </div>
                  <div className="learning-course-stat-card">
                    <span className="learning-course-stat-card-value">{totalMinutes}</span>
                    <span className="learning-course-stat-card-label">预计总时长(分钟)</span>
                  </div>
                </div>
                <div className="learning-course-progress">
                  <div className="progress-bar">
                    <i style={{ width: `${progressPct}%` }} />
                  </div>
                  <span className="muted">
                    {doneCount}/{moduleCount} 讲已完成
                  </span>
                </div>
              </div>
            </header>

            <section className="learning-course-modules-head">
              <div>
                <h3>学习讲次</h3>
                <p>建议按顺序学习；每项资源都可点击进入弹窗查看详情。</p>
              </div>
              <div className="learning-course-modules-actions">
                <button type="button" className="btn-secondary" onClick={expandAll}>
                  展开全部
                </button>
                <button type="button" className="btn-secondary" onClick={collapseAll}>
                  收起全部
                </button>
              </div>
            </section>
            <div className="learning-course-modules learning-course-modules--timeline">
              {course.modules.map((mod, index) => (
                <LearningModuleSection
                  key={mod.id}
                  module={mod}
                  index={index}
                  onOpenResource={setActiveResource}
                  expanded={expandedModuleIds.has(mod.id)}
                  onToggle={() => toggleModule(mod.id)}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {user ? (
        <LearningResourceModal
          open={activeResource !== null}
          resource={activeResource}
          userId={user.id}
          onClose={() => setActiveResource(null)}
        />
      ) : null}
    </AppShell>
  );
}
