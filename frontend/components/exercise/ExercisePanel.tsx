"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { submitPractice } from "@/lib/api";
import type { ExerciseSet } from "@/lib/types";

type ResultRow = {
  score: number;
  standardAnswer: string;
  gradingType: string;
  feedback: string;
};

export function ExercisePanel({
  exerciseSet,
  userId,
  compact = false,
  embedded = false,
  onSubmitted
}: {
  exerciseSet: ExerciseSet;
  userId: string;
  compact?: boolean;
  embedded?: boolean;
  onSubmitted?: (totalScore: number) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [totalScore, setTotalScore] = useState(0);
  const [results, setResults] = useState<Record<string, ResultRow>>({});

  async function handleSubmit() {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await submitPractice(userId, exerciseSet.resourceId, answers);
      const next: Record<string, ResultRow> = {};
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
      setSubmitted(true);
      onSubmitted?.(response.totalScore);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setAnswers({});
    setResults({});
    setSubmitted(false);
    setTotalScore(0);
  }

  return (
    <div className={`exercise-panel${compact ? " exercise-panel-compact" : ""}`}>
      <div className="exercise-panel-head">
        <div>
          <strong>{exerciseSet.title}</strong>
          <p className="muted">{exerciseSet.summary}</p>
        </div>
        {!embedded ? (
          <Link href={`/practice?resource=${encodeURIComponent(exerciseSet.resourceId)}`} className="btn-secondary">
            去练习页
          </Link>
        ) : null}
      </div>

      {error ? <p className="muted" style={{ color: "var(--danger)" }}>{error}</p> : null}

      {exerciseSet.questions.map((q, index) => {
        const result = results[q.id];
        const statusLabel =
          q.attemptStatus === "correct"
            ? "曾答对"
            : q.attemptStatus === "wrong"
              ? "曾答错"
              : q.attemptStatus === "unanswered"
                ? "未作答"
                : null;
        return (
          <div key={q.id} className="question-block">
            <div className="question-head">
              <strong>
                第 {index + 1} 题 · {q.difficulty}
                {q.gradingType === "rubric" ? " · 开放题" : " · 标准答案"}
              </strong>
              {statusLabel ? <span className="muted">{statusLabel}</span> : null}
              {submitted && result ? (
                result.score >= 60 ? (
                  <CheckCircle2 size={18} color="#059669" />
                ) : (
                  <XCircle size={18} color="#dc2626" />
                )
              ) : null}
            </div>
            <p>{q.question}</p>
            <textarea
              rows={3}
              value={answers[q.id] ?? ""}
              disabled={submitted}
              placeholder="输入你的答案..."
              onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
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
      })}

      {exerciseSet.questions.length > 0 ? (
        <div style={{ display: "flex", gap: 10, marginTop: 12, alignItems: "center" }}>
          {!submitted ? (
            <button type="button" className="btn-primary" onClick={handleSubmit} disabled={loading}>
              {loading ? <Loader2 size={16} /> : null}
              {loading ? "提交中..." : "提交答卷"}
            </button>
          ) : (
            <>
              <span className="muted">本次得分：{totalScore} 分</span>
              <button type="button" className="btn-secondary" onClick={handleReset}>
                重新作答
              </button>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
