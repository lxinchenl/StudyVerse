"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  Brain,
  ChevronRight,
  Clock,
  Code2,
  FileText,
  PlayCircle,
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

const TYPE_ICONS: Record<string, typeof FileText> = {
  note: FileText,
  mindmap: Brain,
  video_script: PlayCircle,
  exercise: BookOpen,
  code_lab: Code2
};

function stripModuleTitle(title: string): string {
  return title.replace(/^第\s*\d+\s*讲[：:\s]*/u, "").trim() || title;
}

function LearningModuleSection({
  module,
  index,
  onOpenResource
}: {
  module: LearningModule;
  index: number;
  onOpenResource: (resource: CourseResourceRef) => void;
}) {
  const resources = useMemo(
    () => [...module.resources].sort((a, b) => a.order - b.order),
    [module.resources]
  );
  const displayTitle = stripModuleTitle(module.title);

  return (
    <section className={`learning-module-section learning-module-section--${module.status}`}>
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
        </div>
      </div>

      {resources.length > 0 ? (
        <div className="learning-module-track-wrap">
          <p className="learning-module-track-label">
            <Sparkles size={14} /> 按学习顺序展开
          </p>
          <div className="learning-module-track">
            {resources.map((res, resIndex) => {
              const Icon = TYPE_ICONS[String(res.type)] ?? FileText;
              const typeLabel = RESOURCE_TYPE_LABELS[String(res.type)] ?? String(res.type);
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
                  >
                    <span className="learning-resource-card-order">{res.order}</span>
                    <span className={`learning-resource-card-icon learning-resource-card-icon--${res.type}`}>
                      <Icon size={18} />
                    </span>
                    <span className="learning-resource-card-type">{typeLabel}</span>
                    <strong className="learning-resource-card-title">{res.title}</strong>
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

  useEffect(() => {
    if (!user || !courseId) return;
    fetchLearningCourseDetail(user.id, courseId)
      .then(setCourse)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user, courseId]);

  const doneCount = course?.modules.filter((m) => m.status === "done").length ?? 0;
  const moduleCount = course?.modules.length ?? 0;
  const progressPct = moduleCount ? Math.round((doneCount / moduleCount) * 100) : 0;

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

            <div className="learning-course-modules">
              {course.modules.map((mod, index) => (
                <LearningModuleSection
                  key={mod.id}
                  module={mod}
                  index={index}
                  onOpenResource={setActiveResource}
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
