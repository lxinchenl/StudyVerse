"use client";

import { memo, useMemo } from "react";

import { getAgentMeta, type AgentStatus } from "@/lib/studio-agents";
import type { AgentState } from "./AgentWorkbench";

/** 工位布局 — 参考 Marvis 右侧虚拟办公室 */
const DESK_LAYOUT: Array<{ id: string; col: number; row: number; isLead?: boolean }> = [
  { id: "coordinator-agent", col: 2, row: 1, isLead: true },
  { id: "inquiry-agent", col: 1, row: 2 },
  { id: "retrieval-agent", col: 2, row: 2 },
  { id: "note-agent", col: 3, row: 2 },
  { id: "exercise-agent", col: 1, row: 3 },
  { id: "mindmap-agent", col: 2, row: 3 },
  { id: "video-agent", col: 3, row: 3 },
  { id: "code-lab-agent", col: 2, row: 4 },
];

const STATUS_HINT: Record<AgentStatus, string> = {
  idle: "摸鱼中…",
  working: "敲键盘中",
  done: "任务完成",
  waiting: "等你回复",
  inactive: "离线"
};

const IDLE_POSE = ["☕", "💤", "🎵", "📱"];

function deskPose(agentId: string, status: AgentStatus): string {
  const meta = getAgentMeta(agentId);
  if (status === "working") return meta.emoji;
  if (status === "waiting") return "🙋";
  if (status === "done") return "✅";
  const idx = agentId.charCodeAt(0) % IDLE_POSE.length;
  return IDLE_POSE[idx];
}

function OfficeDesk({
  agent,
  bubble,
}: {
  agent: AgentState | null;
  bubble?: string;
}) {
  if (!agent) {
    return (
      <div className="office-desk office-desk-empty">
        <div className="office-desk-surface" />
        <span className="office-desk-label muted">空工位</span>
      </div>
    );
  }

  const meta = getAgentMeta(agent.id);
  const pose = deskPose(agent.id, agent.status);

  return (
    <div className={`office-desk office-desk-${agent.status}${agent.id === "coordinator-agent" ? " office-desk-lead" : ""}`}>
      {bubble ? <div className="office-bubble">{bubble}</div> : null}
      <div className="office-character" style={{ "--agent-color": meta.color } as React.CSSProperties}>
        <span className="office-character-body">{pose}</span>
        {agent.status === "working" ? <span className="office-typing-dots"><i /><i /><i /></span> : null}
      </div>
      <div className="office-desk-surface">
        <span className="office-monitor" />
        <span className="office-keyboard" />
      </div>
      <div className="office-desk-info">
        <strong>{meta.name}</strong>
        <span className={`office-status-pill ${agent.status}`}>{STATUS_HINT[agent.status]}</span>
      </div>
    </div>
  );
}

interface VirtualOfficeProps {
  agents: AgentState[];
  latestBubbles: Record<string, string>;
  running: boolean;
}

function VirtualOfficeInner({ agents, latestBubbles, running }: VirtualOfficeProps) {
  const agentMap = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);

  const visibleDesks = DESK_LAYOUT.filter(
    (d) => agentMap.has(d.id) || d.id === "coordinator-agent" || d.id === "inquiry-agent" || d.id === "retrieval-agent"
  );

  const workingCount = agents.filter((a) => a.status === "working").length;
  const doneCount = agents.filter((a) => a.status === "done").length;

  return (
    <div className="virtual-office">
      <div className="virtual-office-scene">
        <div className="office-window" aria-hidden>
          <div className="office-window-glow" />
          <div className="office-cityline" />
        </div>

        <div className="office-floor-grid" aria-hidden />

        <div className="office-status-bar">
          <span className={running ? "office-live-dot" : ""}>
            {running ? "协作进行中" : "办公室待命"}
          </span>
          <span>{agents.length} 位 Agent · {workingCount} 工作中 · {doneCount} 已完成</span>
        </div>

        <div className="office-desks">
          {visibleDesks.map((desk) => {
            const agent = agentMap.get(desk.id) ?? null;
            if (!agent && !["coordinator-agent", "inquiry-agent", "retrieval-agent"].includes(desk.id)) {
              return null;
            }
            const defaultAgent: AgentState | null = agent ?? {
              id: desk.id,
              status: "idle",
              role: getAgentMeta(desk.id).name,
            };
            return (
              <div
                key={desk.id}
                className="office-desk-slot"
                style={{ gridColumn: desk.col, gridRow: desk.row }}
              >
                <OfficeDesk agent={defaultAgent} bubble={latestBubbles[desk.id]} />
              </div>
            );
          })}
        </div>

        <div className="office-decor office-plant-left" aria-hidden>🪴</div>
        <div className="office-decor office-plant-right" aria-hidden>🌿</div>
        <div className="office-decor office-water-cooler" aria-hidden>🚰</div>
      </div>
    </div>
  );
}

export const VirtualOffice = memo(VirtualOfficeInner);
