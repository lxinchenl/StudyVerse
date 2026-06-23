"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, BookOpen, FileStack, Gauge } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { ChapterAccordion } from "@/components/courses/ChapterAccordion";
import { fetchChapters, fetchCourses, fetchDocuments } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Chapter, Course, CourseDocument } from "@/lib/types";

export default function CoursePage() {
  const params = useParams<{ courseId: string }>();
  const courseId = params.courseId;
  const { user } = useAuth();
  const [course, setCourse] = useState<Course | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [documents, setDocuments] = useState<CourseDocument[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user || !courseId) return;
    Promise.all([
      fetchCourses(user.id),
      fetchChapters(courseId),
      fetchDocuments(courseId, user.id)
    ])
      .then(([courses, chs, docs]) => {
        setCourse(courses.find((c) => c.id === courseId) ?? null);
        setChapters(chs);
        setDocuments(docs);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user, courseId]);

  if (error) {
    return <AppShell title="加载失败"><p>{error}</p></AppShell>;
  }

  if (!course) {
    return <AppShell title="加载中..."><p className="muted">正在加载课程资料...</p></AppShell>;
  }

  const totalPages = documents.reduce((sum, doc) => sum + (doc.pages ?? 0), 0);

  return (
    <AppShell title="课程详情" subtitle="按章节浏览资料并进入精读">
      <div className="course-detail-page">
        <Link href="/courses" className="btn-secondary course-detail-back">
          <ArrowLeft size={16} />
          返回课程列表
        </Link>

        <section className="course-detail-hero">
          <div>
            <span className="tag">{course.id}</span>
            <h2>{course.title}</h2>
            <p className="course-detail-summary">{course.description}</p>
            <div className="progress-bar course-detail-progress">
              <i style={{ width: `${course.progress}%` }} />
            </div>
          </div>
          <div className="course-detail-stats">
            <div className="course-detail-stat">
              <span className="course-detail-stat-label">
                <BookOpen size={14} />
                章节
              </span>
              <strong>{course.chapterCount}</strong>
            </div>
            <div className="course-detail-stat">
              <span className="course-detail-stat-label">
                <FileStack size={14} />
                资料
              </span>
              <strong>{course.documentCount}</strong>
            </div>
            <div className="course-detail-stat">
              <span className="course-detail-stat-label">
                <Gauge size={14} />
                总页数
              </span>
              <strong>{totalPages || "—"}</strong>
            </div>
            <p className="muted">上次学习 {course.lastStudiedAt || "—"} · 完成度 {course.progress}%</p>
          </div>
        </section>

        <section className="card course-detail-outline">
          <div className="course-detail-outline-head">
            <h3>章节目录</h3>
            <p className="muted">按章节展开查看文档并进入阅读</p>
          </div>
          <ChapterAccordion chapters={chapters} documents={documents} courseId={courseId} />
        </section>
      </div>
    </AppShell>
  );
}
