"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, BookOpen, FileStack, Gauge } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth";
import { fetchCourses } from "@/lib/api";
import type { Course } from "@/lib/types";

export default function CoursesPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [error, setError] = useState("");

  const totals = useMemo(() => {
    const totalDocs = courses.reduce((sum, c) => sum + c.documentCount, 0);
    const avgProgress = courses.length
      ? Math.round(courses.reduce((sum, c) => sum + c.progress, 0) / courses.length)
      : 0;
    return {
      courseCount: courses.length,
      totalDocs,
      avgProgress
    };
  }, [courses]);

  useEffect(() => {
    if (!user) return;
    fetchCourses(user.id)
      .then(setCourses)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user]);

  return (
    <AppShell title="课程资料" subtitle="按课程查看章节与课件，保持连续学习节奏">
      {error ? <p className="muted">{error}</p> : null}
      <section className="course-library-overview">
        <div className="card course-library-kpi">
          <span className="muted">课程总数</span>
          <div className="stat-value">{totals.courseCount}</div>
          <p className="muted">当前已接入课程</p>
        </div>
        <div className="card course-library-kpi">
          <span className="muted">资料总数</span>
          <div className="stat-value">{totals.totalDocs}</div>
          <p className="muted">覆盖课件与讲义文档</p>
        </div>
        <div className="card course-library-kpi">
          <span className="muted">平均完成度</span>
          <div className="stat-value">{totals.avgProgress}%</div>
          <p className="muted">按课程进度均值计算</p>
        </div>
      </section>

      {courses.length === 0 ? (
        <div className="card course-library-empty">
          <h3>还没有课程内容</h3>
          <p className="muted">
            可在 <code>data/courses/{"{course-id}"}/materials/</code> 中添加课件，系统会自动扫描并展示。
          </p>
        </div>
      ) : (
        <section className="course-library-grid">
          {courses.map((course) => (
            <article key={course.id} className="card course-library-card">
              <div className="course-library-card-head">
                <span className="tag">{course.id}</span>
                <span className="course-library-progress-badge">{course.progress}%</span>
              </div>
              <h3>{course.title}</h3>
              <p className="muted">{course.description}</p>
              <div className="course-library-meta">
                <span>
                  <BookOpen size={14} />
                  {course.chapterCount} 章
                </span>
                <span>
                  <FileStack size={14} />
                  {course.documentCount} 份资料
                </span>
                <span>
                  <Gauge size={14} />
                  上次学习 {course.lastStudiedAt || "—"}
                </span>
              </div>
              <div className="progress-bar course-library-progress">
                <i style={{ width: `${course.progress}%` }} />
              </div>
              <Link href={`/courses/${course.id}`} className="btn-secondary course-library-cta">
                进入课程 <ArrowRight size={16} />
              </Link>
            </article>
          ))}
        </section>
      )}
    </AppShell>
  );
}
