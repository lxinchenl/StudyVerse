"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ChevronDown, XCircle } from "lucide-react";

import { QuestionMetaTags } from "@/components/exercise/QuestionMetaTags";
import { AppShell } from "@/components/layout/AppShell";
import { CodeLabPanel } from "@/lib/lazy-components";
import { useAuth } from "@/lib/auth";
import { clearPracticeDraft, readPracticeDraft, savePracticeDraft } from "@/lib/practiceDrafts";
import {
  fetchCodeLabSet,
  fetchExercises,
  fetchPracticeResources,
  fetchProfile,
  submitPractice,
  type PracticeResource
} from "@/lib/api";
import type { CodeLabSet, Exercise, UserProfile } from "@/lib/types";

export default function PracticePage() {
  return (
    <Suspense
      fallback={
        <AppShell title="练习与测评" subtitle="加载中…">
          <p className="muted">加载练习题…</p>
        </AppShell>
      }
    >
      <PracticePageInner />
    </Suspense>
  );
}

function PracticePageInner() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const initialResource = searchParams.get("resource") ?? "";
  const initialKind = searchParams.get("kind");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [resources, setResources] = useState<PracticeResource[]>([]);
  const [questions, setQuestions] = useState<Exercise[]>([]);
  const [labSet, setLabSet] = useState<CodeLabSet | null>(null);
  const [selectedResource, setSelectedResource] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState<
    Record<string, { score: number; standardAnswer: string; gradingType: string; feedback: string }>
  >({});
  const [totalScore, setTotalScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeKind, setActiveKind] = useState<"all" | "exercise" | "code_lab">("all");
  const [exercisePage, setExercisePage] = useState(1);
  const [codeLabPage, setCodeLabPage] = useState(1);
  const [bankCollapsed, setBankCollapsed] = useState(false);
  const PAGE_SIZE = 5;

  const selected = useMemo(
    () => resources.find((r) => r.id === selectedResource),
    [resources, selectedResource]
  );
  const isCodeLab = selected?.kind === "code_lab";
  const exerciseResources = useMemo(() => resources.filter((r) => r.kind === "exercise"), [resources]);
  const codeLabResources = useMemo(() => resources.filter((r) => r.kind === "code_lab"), [resources]);

  useEffect(() => {
    if (!user) return;
    fetchProfile(user.id).then(setProfile).catch(() => {});
    fetchPracticeResources()
      .then((list) => {
        if (initialKind === "exercise" || initialKind === "code_lab") {
          setActiveKind(initialKind);
        }
        setResources(list);
        if (initialResource && list.some((r) => r.id === initialResource)) {
          setSelectedResource(initialResource);
        } else if (list[0]) {
          setSelectedResource(list[0].id);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user, initialResource, initialKind]);

  useEffect(() => {
    if (!selectedResource || !user) return;
    const resource = resources.find((r) => r.id === selectedResource);
    if (!resource) return;

    setError("");
    setResults({});
    setSubmitted(false);
    setTotalScore(0);
    setQuestions([]);
    setLabSet(null);
    setAnswers(resource.kind === "exercise" ? readPracticeDraft(user.id, selectedResource) : {});

    if (resource.kind === "code_lab") {
      fetchCodeLabSet(user.id, selectedResource)
        .then(setLabSet)
        .catch((e) => setError(e instanceof Error ? e.message : "加载编程题失败"));
      return;
    }

    fetchExercises(selectedResource)
      .then(setQuestions)
      .catch((e) => setError(e instanceof Error ? e.message : "加载题目失败"));
  }, [selectedResource, resources, user]);

  async function handleSubmit() {
    if (!user || !selectedResource || loading || isCodeLab) return;
    setLoading(true);
    setError("");
    try {
      const response = await submitPractice(user.id, selectedResource, answers);
      const next: Record<string, { score: number; standardAnswer: string; gradingType: string; feedback: string }> =
        {};
      response.results.forEach((r) => {
        next[r.questionId] = {
          score: r.score,
          standardAnswer: r.standardAnswer,
          gradingType: r.gradingType,
          feedback: r.feedback
        };
      });
      setResults(next);
      setTotalScore(response.totalScore);
      setProfile(response.profile);
      setSubmitted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  function handleAnswerChange(questionId: string, value: string) {
    if (!user || !selectedResource) return;
    setAnswers((prev) => {
      const next = { ...prev, [questionId]: value };
      savePracticeDraft(user.id, selectedResource, next);
      return next;
    });
  }

  function handleReset() {
    setAnswers({});
    setResults({});
    setSubmitted(false);
    setTotalScore(0);
    if (user && selectedResource) {
      clearPracticeDraft(user.id, selectedResource);
    }
  }

  function renderResourceGroup(
    title: string,
    kind: "exercise" | "code_lab",
    list: PracticeResource[],
    emptyLabel: string
  ) {
    if (activeKind !== "all" && activeKind !== kind) return null;
    const currentPage = kind === "exercise" ? exercisePage : codeLabPage;
    const totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
    const safePage = Math.min(currentPage, totalPages);
    const start = (safePage - 1) * PAGE_SIZE;
    const pageItems = list.slice(start, start + PAGE_SIZE);

    const setPage = (nextPage: number) => {
      if (kind === "exercise") setExercisePage(nextPage);
      else setCodeLabPage(nextPage);
    };

    return (
      <div className="practice-group" key={kind}>
        <div className="practice-group-head">
          <strong>{title}</strong>
          <span>{list.length} 个题库</span>
        </div>
        {list.length === 0 ? (
          <p className="muted">{emptyLabel}</p>
        ) : (
          <>
            <div className="practice-resource-list">
              {pageItems.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={selectedResource === r.id ? "practice-resource-btn active" : "practice-resource-btn"}
                  onClick={() => {
                    setSelectedResource(r.id);
                  }}
                >
                  <span className="practice-resource-title">{r.title}</span>
                  <span className="practice-resource-meta">{kind === "code_lab" ? "实操题集" : "练习题集"}</span>
                </button>
              ))}
            </div>
            <div className="practice-pagination">
              <button
                type="button"
                className="practice-page-btn"
                disabled={safePage <= 1}
                onClick={() => setPage(Math.max(1, safePage - 1))}
              >
                上一页
              </button>
              <span className="practice-page-indicator">
                第 {safePage} / {totalPages} 页
              </span>
              <button
                type="button"
                className="practice-page-btn"
                disabled={safePage >= totalPages}
                onClick={() => setPage(Math.min(totalPages, safePage + 1))}
              >
                下一页
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <AppShell
      title="练习与测评"
      subtitle="标准练习与实操编程统一管理，提交后同步学习画像"
    >
      {error ? <p className="muted" style={{ color: "var(--danger)" }}>{error}</p> : null}
      <section className="practice-overview">
        <div className="card practice-kpi">
          <span className="muted">当前用户</span>
          <div className="stat-value">{user?.name}</div>
        </div>
        <div className="card practice-kpi">
          <span className="muted">评分结果</span>
          <div className="stat-value">{submitted && !isCodeLab ? `${totalScore} 分` : "-"}</div>
        </div>
        <div className="card practice-kpi">
          <span className="muted">常错点数量</span>
          <div className="stat-value">{profile?.frequentErrors.length ?? 0}</div>
          <p>{profile?.frequentErrors.join("、") ?? "-"}</p>
        </div>
      </section>

      <section className="card practice-bank">
        <div className="practice-bank-head">
          <button
            type="button"
            className="practice-bank-toggle"
            onClick={() => setBankCollapsed((v) => !v)}
            aria-expanded={!bankCollapsed}
          >
            <span>题库分类</span>
            <ChevronDown size={16} className={bankCollapsed ? "practice-bank-toggle-icon collapsed" : "practice-bank-toggle-icon"} />
          </button>
          {!bankCollapsed ? (
            <div className="practice-filter">
              <button
                type="button"
                className={activeKind === "all" ? "practice-filter-btn active" : "practice-filter-btn"}
                onClick={() => setActiveKind("all")}
              >
                全部
              </button>
              <button
                type="button"
                className={activeKind === "exercise" ? "practice-filter-btn active" : "practice-filter-btn"}
                onClick={() => setActiveKind("exercise")}
              >
                练习题
              </button>
              <button
                type="button"
                className={activeKind === "code_lab" ? "practice-filter-btn active" : "practice-filter-btn"}
                onClick={() => setActiveKind("code_lab")}
              >
                实操题
              </button>
            </div>
          ) : null}
        </div>
        {!bankCollapsed ? (
          resources.length === 0 ? (
            <p className="muted">
              暂无题目。可在学习对话中请求生成练习题或实操题，生成后会自动出现在此处。
            </p>
          ) : (
            <div className="practice-groups">
              {renderResourceGroup("练习题库", "exercise", exerciseResources, "暂无练习题")}
              {renderResourceGroup("实操题库", "code_lab", codeLabResources, "暂无实操题")}
            </div>
          )
        ) : (
          <p className="practice-bank-collapsed-hint">
            已收起 · 共 {resources.length} 个题库
          </p>
        )}
      </section>

      {resources.length > 0 && selected ? (
        <section className="card practice-content">
          <div className="practice-content-head">
            <h3>{selected.title}</h3>
            <span className="practice-content-kind">
              {selected.kind === "code_lab" ? "实操题" : "练习题"}
            </span>
          </div>
          {isCodeLab ? (
            labSet ? (
              <CodeLabPanel labSet={labSet} userId={user?.id ?? ""} />
            ) : (
              <p className="muted">加载编程题…</p>
            )
          ) : questions.length === 0 ? (
            <p className="muted">该题库暂无题目。</p>
          ) : (
            <>
              {questions.map((q, index) => (
                <QuestionBlock
                  key={q.id}
                  index={index + 1}
                  question={q}
                  answer={answers[q.id] ?? ""}
                  result={results[q.id]}
                  submitted={submitted}
                  onChange={(v) => handleAnswerChange(q.id, v)}
                />
              ))}
              <div className="practice-actions">
                {!submitted ? (
                  <button type="button" className="btn-primary" onClick={handleSubmit} disabled={loading}>
                    {loading ? "提交中..." : "提交答卷"}
                  </button>
                ) : (
                  <button type="button" className="btn-secondary" onClick={handleReset}>
                    重新作答
                  </button>
                )}
                {!submitted ? (
                  <button type="button" className="btn-secondary" onClick={handleReset}>
                    重置
                  </button>
                ) : null}
              </div>
            </>
          )}
        </section>
      ) : null}
    </AppShell>
  );
}

function QuestionBlock({
  index,
  question,
  answer,
  result,
  submitted,
  onChange
}: {
  index: number;
  question: Exercise;
  answer: string;
  result?: { score: number; standardAnswer: string; gradingType: string; feedback: string };
  submitted: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="question-block">
      <div className="question-head">
        <div className="question-title-row">
          <strong>第 {index} 题</strong>
          <QuestionMetaTags difficulty={question.difficulty} gradingType={question.gradingType} />
        </div>
        {submitted && result ? (
          result.score >= 60 ? <CheckCircle2 size={18} color="#059669" /> : <XCircle size={18} color="#dc2626" />
        ) : null}
      </div>
      <p>{question.question}</p>
      <textarea
        rows={3}
        value={answer}
        disabled={submitted}
        placeholder="输入你的答案..."
        onChange={(e) => onChange(e.target.value)}
      />
      {submitted && result ? (
        <div className="answer-reveal">
          <p>
            <strong>得分：{result.score} 分</strong>
          </p>
          {result.gradingType === "rubric" ? (
            <>
              <p className="muted">评分标准：{result.standardAnswer}</p>
              {result.feedback ? <p className="muted">评语：{result.feedback}</p> : null}
            </>
          ) : (
            <p className="muted">标准答案：{result.standardAnswer}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
