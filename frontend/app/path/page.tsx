"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth";
import { fetchLearningCourses } from "@/lib/api";
import type { LearningCourseSummary } from "@/lib/types";

export default function PathPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<LearningCourseSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    fetchLearningCourses(user.id)
      .then(setCourses)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user]);

  return (
    <AppShell title="学习路径" subtitle="定制系统课与阶段性学习计划">
      {error ? <p className="muted">{error}</p> : null}
      {courses.length === 0 ? (
        <div className="card">
          <p className="muted">
            暂无定制课。可在学习对话中说「我想系统学 xxx」或「帮我安排一门课」，Agent 会先询问你是否需要生成针对性课程。
          </p>
        </div>
      ) : (
        <div className="learning-course-grid">
          {courses.map((course) => (
            <Link key={course.id} href={`/path/${course.id}`} className="card learning-course-card">
              <div className="learning-course-card-head">
                <h3>{course.title}</h3>
                <span className="tag">{Math.round(course.progress * 100)}%</span>
              </div>
              <p className="muted">{course.summary || course.topic}</p>
              <p className="muted learning-course-meta">
                {course.moduleCount} 讲 · 创建于 {course.createdAt}
              </p>
              <div className="progress-bar">
                <i style={{ width: `${Math.round(course.progress * 100)}%` }} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
