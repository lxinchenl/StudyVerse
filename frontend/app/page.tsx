"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { AnimatedText } from "@/components/ui/animated-shiny-text";
import { useAuth } from "@/lib/auth";
import { fetchCourses, fetchPracticeResources, fetchProfile, type PracticeResource } from "@/lib/api";
import type { Course, UserProfile } from "@/lib/types";

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

export default function HomePage() {
  const { user } = useAuth();
  const [course, setCourse] = useState<Course | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [nextPractice, setNextPractice] = useState<PracticeResource | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    Promise.all([fetchCourses(user.id), fetchProfile(user.id), fetchPracticeResources()])
      .then(([courses, prof, resources]) => {
        setCourse(courses[0] ?? null);
        setProfile(prof);
        setNextPractice(resources[0] ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user]);

  // 一个安静的时间问候，替代原先的大段 hero 标语
  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 6) return "夜深了";
    if (h < 11) return "早上好";
    if (h < 14) return "中午好";
    if (h < 18) return "下午好";
    return "晚上好";
  }, []);

  const dateLabel = useMemo(() => {
    const d = new Date();
    return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · ${WEEKDAYS[d.getDay()]}`;
  }, []);

  const nextStepTitle = nextPractice?.title || `《${profile?.weakPoints?.[0] ?? "核心概念"}》练习`;
  const nextStepHint =
    nextPractice?.kind === "code_lab" ? "为你匹配了最新实操题集，建议直接动手练习。" : "为你匹配了最新练习题集，建议先完成一轮巩固。";
  const nextStepHref = nextPractice
    ? `/practice?resource=${encodeURIComponent(nextPractice.id)}&kind=${nextPractice.kind}`
    : "/practice";

  return (
    <AppShell>
      <header className="home-top">
        <p className="home-date">{dateLabel}</p>
        <h1 className="home-greet">
          {greeting}，{user?.name ?? "同学"}
        </h1>
      </header>

      {error ? <p className="muted">{error}</p> : null}

      {course ? (
        <section className="home-continue">
          <div className="home-continue-head">
            <span className="home-eyebrow">继续学习</span>
            <Link href="/courses" className="home-link">
              查看课程
            </Link>
          </div>

          <Link href={`/courses/${course.id}`} className="home-continue-main">
            <AnimatedText
              text={course.title}
              className="home-continue-title"
              textClassName="text-[1.9rem] md:text-[2.4rem] font-semibold leading-tight"
              gradientColors="linear-gradient(90deg, #94a3b8 0%, #cbd5e1 42%, #ffffff 49%, #ffffff 51%, #cbd5e1 58%, #94a3b8 100%)"
              gradientAnimationDuration={2.2}
              hoverEffect={false}
            />
            <div className="home-continue-meta">
              <span>上次学习 {course.lastStudiedAt || "—"}</span>
              <span className="home-dot" />
              <span>已完成 {course.progress}%</span>
            </div>
            <div className="home-progress" aria-label="学习进度">
              <i style={{ width: `${course.progress}%` }} />
            </div>
            <div className="home-continue-cta">继续学习</div>
          </Link>
        </section>
      ) : (
        <section className="home-empty">
          <p>还没有课程。</p>
          <Link href="/courses" className="home-link">
            浏览课程
          </Link>
        </section>
      )}

      <section className="home-row">
        <div className="home-tile">
          <span className="home-eyebrow">下一步</span>
          <p className="home-tile-title">{nextStepTitle}</p>
          <p className="home-tile-sub">{nextStepHint}</p>
          <Link href={nextStepHref} className="home-link">
            开始练习
          </Link>
        </div>

        <div className="home-tile">
          <span className="home-eyebrow">本周概览</span>
          <ul className="home-mini">
            <li>
              <span>薄弱点</span>
              <span>{profile?.weakPoints.length ?? 0}</span>
            </li>
            <li>
              <span>近期主题</span>
              <span>{profile?.recentTopics.length ?? 0}</span>
            </li>
            <li>
              <span>学习目标</span>
              <span>{profile?.goal ? "已设置" : "待设置"}</span>
            </li>
          </ul>
          <Link href="/path" className="home-link">
            查看学习路径
          </Link>
        </div>
      </section>

      <nav className="home-shortcuts">
        <Link href="/learn">多 Agent 对话</Link>
        <span className="home-sep" />
        <Link href="/resources">资源库</Link>
        <span className="home-sep" />
        <Link href="/practice">练习</Link>
        <span className="home-sep" />
        <Link href="/settings">设置</Link>
      </nav>
    </AppShell>
  );
}
