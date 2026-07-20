"use client";

import { Activity, BrainCircuit, FileSearch, ShieldCheck, Wrench } from "lucide-react";

import { AgentPlanning, type PlanStep } from "@/components/ui/ai-planning";
import type { AgentTrace, ReactStep } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  reply: "直接回复",
  finish: "完成推理，生成回答",
  call_expert: "调用专家",
  call_tool: "调用工具",
  call_skill: "调用 Skill"
};

const EXPERT_LABELS: Record<string, string> = {
  "retrieval-agent": "检索 Agent",
  "exercise-agent": "练习题 Agent",
  "note-agent": "笔记 Agent",
  "mindmap-agent": "思维导图 Agent",
  "video-agent": "讲解视频 Agent",
  "code-lab-agent": "实操案例 Agent",
  "path-agent": "路径规划 Agent",
  "safety-agent": "安全审校 Agent"
};

const NOTE_STEP_LABELS: Record<string, string> = {
  analyze_intent: "分析笔记意图",
  list_catalog: "查看章节目录",
  extract_material: "提取课件资料",
  vision_analyze: "豆包视觉识图",
  analyze_structure: "分析章节结构",
  compose_notes: "撰写 Markdown 笔记",
  finish: "完成笔记生成",
  plan_next: "规划下一步"
};

const COURSE_STEP_LABELS: Record<string, string> = {
  plan_course: "编排课程大纲",
  module_react: "讲次自主编排",
  generate_resource: "按序生成资源",
  finish_module: "完成本讲编排",
  orchestrate_module: "LLM 编排本讲资源",
  save_path: "同步学习路径",
  plan_next: "规划下一步"
};

function formatAction(step: ReactStep): string {
  const base = ACTION_LABELS[step.action] ?? step.action;
  if (step.action === "call_expert" && step.expert) {
    const modeBlock =
      step.expert === "exercise-agent"
        ? step.exercise
        : step.expert === "code-lab-agent"
          ? step.codeLab
          : undefined;
    const mode =
      modeBlock?.mode ? ` · ${modeBlock.mode === "generate" ? "生成" : "查找"}` : "";
    return `${base} · ${EXPERT_LABELS[step.expert] ?? step.expert}${mode}`;
  }
  if (step.action === "call_tool" && step.tool) {
    return `${base} · ${step.tool}`;
  }
  if (step.action === "call_skill" && step.skill) {
    return `${base} · ${step.skill}`;
  }
  if (step.action.startsWith("note:")) {
    const key = step.action.slice(5);
    return `笔记 Agent · ${NOTE_STEP_LABELS[key] ?? key}`;
  }
  if (step.action.startsWith("course:")) {
    const key = step.action.slice(7);
    return `定制课 Workflow · ${COURSE_STEP_LABELS[key] ?? key}`;
  }
  return base;
}

function stepsSummary(steps: ReactStep[], loading: boolean, statusMessage?: string): string {
  if (loading && steps.length === 0) {
    return statusMessage ?? "推理中…";
  }
  if (steps.length === 0) return "";
  const last = steps[steps.length - 1];
  const action = formatAction(last);
  const running = steps.some((s) => s.status === "running");
  if (running) {
    if (statusMessage?.trim()) {
      return `${steps.length} 步 · ${statusMessage.trim()}`;
    }
    return `${steps.length} 步 · 进行中 · ${action}`;
  }
  return `${steps.length} 步 · ${action}`;
}

export function ReActSteps({
  steps,
  traces,
  loading = false,
  statusMessage
}: {
  steps?: ReactStep[];
  traces?: AgentTrace[];
  loading?: boolean;
  statusMessage?: string;
}) {
  const stepList = steps ?? [];

  if (!loading && stepList.length === 0) return null;

  const summary = stepsSummary(stepList, loading, statusMessage) || "推理中…";

  const planSteps: PlanStep[] =
    loading && stepList.length === 0
      ? [
          {
            id: "react-loading",
            title: statusMessage ?? "主 Agent 正在规划 Thought → Action → Observation",
            status: "active",
            icon: <BrainCircuit className="size-3.5" />,
            defaultExpanded: true,
            content: (
              <div className="planning-rich-content">
                <p className="planning-muted-line">等待模型响应并生成下一步 action…</p>
              </div>
            )
          }
        ]
      : stepList.map((step, index) => {
          const expertTrace =
            step.action === "call_expert" && step.expert && step.status === "done"
              ? traces?.find((t) => t.agent === step.expert)
              : undefined;
          const isActive = step.status === "running";
          const isDone = !step.status || step.status === "done";
          const status: PlanStep["status"] = isActive ? "active" : isDone ? "success" : "pending";

          const icon =
            step.action === "call_expert" ? (
              <FileSearch className="size-3.5" />
            ) : step.action === "call_tool" ? (
              <Wrench className="size-3.5" />
            ) : step.action === "call_skill" ? (
              <ShieldCheck className="size-3.5" />
            ) : (
              <Activity className="size-3.5" />
            );

          return {
            id: `react-${step.step ?? index}`,
            title: formatAction(step),
            status,
            icon,
            defaultExpanded: isActive || index === stepList.length - 1,
            content: (
              <div className="planning-rich-content">
                {step.thought ? <p><strong>Thought</strong>：{step.thought}</p> : null}
                {step.observation ? <p><strong>Observation</strong>：{step.observation}</p> : null}
                {isActive && statusMessage?.trim() && statusMessage.trim() !== step.observation ? (
                  <p className="planning-muted-line planning-status-live">{statusMessage.trim()}</p>
                ) : null}
                {isActive && !step.observation && !statusMessage ? (
                  <p className="planning-muted-line">执行中…</p>
                ) : null}
                {expertTrace ? <p className="planning-muted-line">{expertTrace.summary}</p> : null}
              </div>
            )
          };
        });

  return (
    <div className={`react-steps${loading && stepList.length === 0 ? " react-steps-loading" : ""}`}>
      <AgentPlanning title={`ReAct 推理过程 · ${summary}`} steps={planSteps} />
    </div>
  );
}
