"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { DocumentReader } from "@/components/reader/DocumentReader";
import { fetchCourses, fetchDocument } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Course, CourseDocument } from "@/lib/types";

export default function ReadPage() {
  const params = useParams<{ courseId: string; docId: string }>();
  const { courseId, docId } = params;
  const { user } = useAuth();
  const [course, setCourse] = useState<Course | null>(null);
  const [document, setDocument] = useState<CourseDocument | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user || !courseId || !docId) return;
    Promise.all([fetchCourses(user.id), fetchDocument(docId, user.id)])
      .then(([courses, doc]) => {
        setCourse(courses.find((c) => c.id === courseId) ?? null);
        setDocument(doc);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user, courseId, docId]);

  if (error) {
    return <AppShell title="加载失败"><p>{error}</p></AppShell>;
  }

  if (!course || !document || !user) {
    return <AppShell title="加载中..."><p className="muted">正在加载资料...</p></AppShell>;
  }

  return (
    <AppShell title={document.title} subtitle={`${course.title} · 资料阅读`}>
      <Link href={`/courses/${courseId}`} className="btn-secondary" style={{ marginBottom: 16, display: "inline-flex" }}>
        <ArrowLeft size={16} /> 返回课程资料
      </Link>
      <DocumentReader document={document} userId={user.id} courseId={courseId} />
    </AppShell>
  );
}
