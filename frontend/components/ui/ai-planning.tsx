"use client";

import React, { useRef, useState } from "react";
import {
  BrainCircuit,
  Check,
  ChevronDown,
  ChevronRight,
  Loader2
} from "lucide-react";

export type PlanStepStatus = "pending" | "active" | "success" | "error";

export interface PlanStep {
  id: string;
  title: string;
  content?: React.ReactNode;
  status: PlanStepStatus;
  icon?: React.ReactNode;
  duration?: string;
  defaultExpanded?: boolean;
}

export interface AgentPlanningProps {
  title?: string;
  steps: PlanStep[];
  defaultExpanded?: boolean;
}

export function AgentPlanning({
  title = "Agent 正在规划",
  steps,
  defaultExpanded = false
}: AgentPlanningProps) {
  const [isMainExpanded, setIsMainExpanded] = useState(defaultExpanded);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>(
    steps.reduce(
      (acc, step) => {
        acc[step.id] = step.defaultExpanded || false;
        return acc;
      },
      {} as Record<string, boolean>
    )
  );
  const mainContentRef = useRef<HTMLDivElement>(null);

  const hasActive = steps.some((s) => s.status === "active");
  const allSuccess = steps.length > 0 && steps.every((s) => s.status === "success");

  const getStatusClass = (status: PlanStepStatus) => {
    switch (status) {
      case "success":
        return "planning-step-dot-success";
      case "active":
        return "planning-step-dot-active";
      case "error":
        return "planning-step-dot-error";
      default:
        return "planning-step-dot-pending";
    }
  };

  const toggleStep = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="agent-planning">
      <div className="agent-planning-card">
        <button
          type="button"
          onClick={() => setIsMainExpanded((v) => !v)}
          className="agent-planning-header"
        >
          <div className="agent-planning-title-wrap">
            <span className="agent-planning-main-icon" aria-hidden>
              {hasActive ? (
                <Loader2 className="size-4 animate-spin" />
              ) : allSuccess ? (
                <Check className="size-4" />
              ) : (
                <BrainCircuit className="size-4" />
              )}
            </span>
            <span className="agent-planning-title">{title}</span>
          </div>

          <span className="agent-planning-chevron" aria-hidden>
            {isMainExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </span>
        </button>

        <div className={`agent-planning-body-wrap ${isMainExpanded ? "expanded" : "collapsed"}`}>
          <div ref={mainContentRef} className="agent-planning-body">
            {steps.map((step, index) => {
              const isLast = index === steps.length - 1;
              const isStepExpanded = expandedSteps[step.id];
              return (
                <div key={step.id} className="planning-step">
                  {!isLast ? <div className="planning-step-line" aria-hidden /> : null}
                  <div className={`planning-step-dot ${getStatusClass(step.status)}`}>
                    {step.status === "success" ? (
                      <Check className="size-3.5" />
                    ) : step.status === "active" ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      step.icon || <span className="planning-step-dot-inner" />
                    )}
                  </div>

                  <div className={`planning-step-content ${step.status === "pending" ? "pending" : ""}`}>
                    <div
                      className={`planning-step-head ${step.content ? "clickable" : ""}`}
                      onClick={(e) => step.content && toggleStep(step.id, e)}
                      role={step.content ? "button" : undefined}
                      tabIndex={step.content ? 0 : undefined}
                    >
                      <span className="planning-step-title">{step.title}</span>
                      <div className="planning-step-head-right">
                        {step.duration ? <span className="planning-step-duration">{step.duration}</span> : null}
                        {step.content ? (
                          <span className="planning-step-chevron" aria-hidden>
                            {isStepExpanded ? (
                              <ChevronDown className="size-4" />
                            ) : (
                              <ChevronRight className="size-4" />
                            )}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {step.content ? (
                      <div className={`planning-step-detail ${isStepExpanded ? "expanded" : "collapsed"}`}>
                        <div className="planning-step-detail-inner">{step.content}</div>
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AgentPlanning;
