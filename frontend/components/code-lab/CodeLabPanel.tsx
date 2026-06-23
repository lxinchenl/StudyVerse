"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Play, XCircle } from "lucide-react";

import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer";
import { fetchCodeLabSet, runCodeLab, submitCodeLab } from "@/lib/api";
import type { CodeLabSet } from "@/lib/types";

type RunResult = { stdout: string; stderr: string; ok: boolean };
type SubmitResult = {
  score: number;
  passed: boolean;
  expectedStdout: string;
  actualStdout: string;
  feedback: string;
};

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "简单",
  medium: "中等",
  hard: "困难"
};

export function CodeLabPanel({
  labSet,
  userId,
  compact = false
}: {
  labSet: CodeLabSet;
  userId: string;
  compact?: boolean;
}) {
  const [codes, setCodes] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    labSet.challenges.forEach((c) => {
      init[c.id] = c.starterCode || "";
    });
    return init;
  });
  const [runResults, setRunResults] = useState<Record<string, RunResult>>({});
  const [submitResults, setSubmitResults] = useState<Record<string, SubmitResult>>({});
  const [runningId, setRunningId] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [totalScore, setTotalScore] = useState(0);

  useEffect(() => {
    if (!userId || !labSet.resourceId) return;
    let cancelled = false;
    fetchCodeLabSet(userId, labSet.resourceId)
      .then((fresh) => {
        if (cancelled) return;
        setCodes(() => {
          const init: Record<string, string> = {};
          fresh.challenges.forEach((c) => {
            init[c.id] = c.starterCode || "";
          });
          return init;
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [userId, labSet.resourceId]);

  async function handleRun(challengeId: string) {
    if (runningId) return;
    setRunningId(challengeId);
    setError("");
    try {
      const res = await runCodeLab(userId, labSet.resourceId, challengeId, codes[challengeId] ?? "");
      setRunResults((prev) => ({
        ...prev,
        [challengeId]: { stdout: res.stdout, stderr: res.stderr, ok: res.ok }
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "运行失败");
    } finally {
      setRunningId("");
    }
  }

  async function handleSubmit() {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await submitCodeLab(userId, labSet.resourceId, codes);
      const next: Record<string, SubmitResult> = {};
      res.results.forEach((r) => {
        next[r.challengeId] = {
          score: r.score,
          passed: r.passed,
          expectedStdout: r.expectedStdout,
          actualStdout: r.actualStdout,
          feedback: r.feedback
        };
      });
      setSubmitResults(next);
      setTotalScore(res.totalScore);
      setSubmitted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`code-lab-panel${compact ? " code-lab-panel-compact" : ""}`}>
      <div className="code-lab-panel-head">
        <div>
          <strong>{labSet.title}</strong>
          <p className="muted">{labSet.summary}</p>
        </div>
      </div>

      {error ? <p className="muted" style={{ color: "var(--danger)" }}>{error}</p> : null}

      {labSet.challenges.map((c, index) => {
        const run = runResults[c.id];
        const result = submitResults[c.id];
        return (
          <div key={c.id} className="code-lab-challenge">
            <div className="question-head">
              <strong>
                第 {index + 1} 题 · {DIFFICULTY_LABELS[c.difficulty] ?? c.difficulty} · Python
              </strong>
              {c.topic ? <span className="code-lab-topic-tag">{c.topic}</span> : null}
              {submitted && result ? (
                result.passed ? (
                  <CheckCircle2 size={18} color="#059669" />
                ) : (
                  <XCircle size={18} color="#dc2626" />
                )
              ) : null}
            </div>
            <div className="code-lab-question-body">
              <MarkdownRenderer content={c.question} />
            </div>
            {c.hint ? <p className="code-lab-hint">提示：{c.hint}</p> : null}
            <textarea
              className="code-lab-editor"
              rows={12}
              spellCheck={false}
              value={codes[c.id] ?? ""}
              disabled={submitted}
              onChange={(e) => setCodes((prev) => ({ ...prev, [c.id]: e.target.value }))}
            />
            <div className="code-lab-actions">
              <button
                type="button"
                className="btn-secondary"
                disabled={submitted || runningId === c.id}
                onClick={() => handleRun(c.id)}
              >
                {runningId === c.id ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                运行
              </button>
            </div>
            {run ? (
              <div className="code-lab-output">
                <strong>运行输出</strong>
                <pre>{run.stdout || "（无 stdout）"}</pre>
                {run.stderr ? <pre className="code-lab-stderr">{run.stderr}</pre> : null}
              </div>
            ) : null}
            {submitted && result ? (
              <div className="answer-reveal">
                <p>
                  <strong>{result.passed ? "通过" : "未通过"}</strong> · 得分 {result.score}
                </p>
                <p className="muted">{result.feedback}</p>
                {!result.passed && result.expectedStdout ? (
                  <details>
                    <summary>查看期望输出</summary>
                    <pre>{result.expectedStdout}</pre>
                  </details>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}

      <div className="code-lab-footer">
        {submitted ? (
          <p>
            <strong>总得分：{totalScore}</strong>
          </p>
        ) : (
          <button type="button" className="btn-primary" disabled={loading} onClick={handleSubmit}>
            {loading ? <Loader2 size={16} className="spin" /> : null}
            提交判题
          </button>
        )}
      </div>
    </div>
  );
}
