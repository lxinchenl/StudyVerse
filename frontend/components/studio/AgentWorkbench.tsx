"use client";

import { memo } from "react";

import { getAgentMeta, type AgentStatus } from "@/lib/studio-agents";

export interface AgentState {
  id: string;
  status: AgentStatus;
  role?: string;
}

const STATUS_LABEL: Record<AgentStatus, string> = {
  idle: "待命",
  working: "工作中",
  done: "完成",
  waiting: "等待回复",
  inactive: "未激活"
};

interface AgentWorkbenchProps {
  agents: AgentState[];
}

function AgentCard({ agent }: { agent: AgentState }) {
  const meta = getAgentMeta(agent.id);
  return (
    <div className={`studio-agent-card ${agent.status}`}>
      <div
        className="studio-agent-avatar"
        style={{ background: `${meta.color}18`, color: meta.color }}
      >
        {meta.emoji}
      </div>
      <div className="studio-agent-info">
        <strong>{meta.name}</strong>
        <span>{agent.role ?? meta.name}</span>
      </div>
      <span className={`studio-agent-status ${agent.status}`}>
        {STATUS_LABEL[agent.status]}
      </span>
    </div>
  );
}

function AgentWorkbenchInner({ agents }: AgentWorkbenchProps) {
  return (
    <div className="studio-workbench">
      <p className="studio-workbench-title">Agent 工作台</p>
      {agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} />
      ))}
    </div>
  );
}

export const AgentWorkbench = memo(AgentWorkbenchInner);
