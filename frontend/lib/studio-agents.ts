export type AgentStatus = "idle" | "working" | "done" | "waiting" | "inactive";

export type OfficeCharacterKind = "agent" | "npc";

export interface StudioAgentMeta {
  id: string;
  name: string;
  shortName: string;
  emoji: string;
  color: string;
  desk: string;
  role: string;
  /** agent = 有 LLM 的生产角色；npc = 固定流程工具，地图上可见但无内置模型 */
  kind: OfficeCharacterKind;
}

/** 有 LLM、在工位上生产的 Agent */
export const STUDIO_ROSTER: StudioAgentMeta[] = [
  {
    id: "retrieval-agent",
    name: "检索 Agent",
    shortName: "检索",
    emoji: "🔍",
    color: "#36D6FF",
    desk: "retrieval",
    role: "课程资料与图谱",
    kind: "agent",
  },
  {
    id: "exercise-agent",
    name: "练习题 Agent",
    shortName: "练习",
    emoji: "📝",
    color: "#3DD68C",
    desk: "exercise",
    role: "出题与组卷",
    kind: "agent",
  },
  {
    id: "note-agent",
    name: "笔记 Agent",
    shortName: "笔记",
    emoji: "📒",
    color: "#B37FEB",
    desk: "note",
    role: "结构化笔记",
    kind: "agent",
  },
  {
    id: "mindmap-agent",
    name: "导图 Agent",
    shortName: "导图",
    emoji: "🧠",
    color: "#F759AB",
    desk: "mindmap",
    role: "思维导图",
    kind: "agent",
  },
  {
    id: "video-agent",
    name: "视频 Agent",
    shortName: "视频",
    emoji: "🎬",
    color: "#FF8C42",
    desk: "video",
    role: "讲解动画",
    kind: "agent",
  },
  {
    id: "code-lab-agent",
    name: "实操 Agent",
    shortName: "实操",
    emoji: "💻",
    color: "#2EE6E6",
    desk: "codelab",
    role: "实验案例",
    kind: "agent",
  },
];

/**
 * 流程 NPC：占工位、地图上可见，由固定逻辑驱动（非 LLM）
 * - 询问员：MsgHub 需要用户补充时激活侧栏问询，收集后转给对应 Agent
 * - 数据管理员：资源入库时从工位走到生产 Agent → 书柜，表示归档
 */
export const STUDIO_NPCS: StudioAgentMeta[] = [
  {
    id: "inquiry-desk",
    name: "询问员",
    shortName: "询问",
    emoji: "💬",
    color: "#FFB020",
    desk: "inquiry",
    role: "收集用户补充信息",
    kind: "npc",
  },
  {
    id: "data-archivist",
    name: "数据管理员",
    shortName: "归档",
    emoji: "📚",
    color: "#8B7355",
    desk: "archive",
    role: "资料存入文档库",
    kind: "npc",
  },
];

/** 地图上所有占工位角色（NPC 在前，便于图层/遍历） */
export const OFFICE_CHARACTERS: StudioAgentMeta[] = [...STUDIO_NPCS, ...STUDIO_ROSTER];

export const STUDIO_AGENT_META: Record<string, StudioAgentMeta> = Object.fromEntries(
  OFFICE_CHARACTERS.map((a) => [a.id, a])
);

/** 后端 hub / agent_status 仍可能用旧 id，映射到办公室角色 */
export const HUB_AGENT_ALIASES: Record<string, string> = {
  "inquiry-agent": "inquiry-desk",
};

export function resolveOfficeCharacterId(agentId: string): string {
  return HUB_AGENT_ALIASES[agentId] ?? agentId;
}

export function getAgentMeta(agentId: string): StudioAgentMeta {
  const id = resolveOfficeCharacterId(agentId);
  return (
    STUDIO_AGENT_META[id] ?? {
      id: agentId,
      name: agentId,
      shortName: agentId.slice(0, 4),
      emoji: "🤖",
      color: "#86909C",
      desk: "extra",
      role: "Agent",
      kind: "agent",
    }
  );
}

export function isOfficeNpc(agentId: string): boolean {
  return getAgentMeta(agentId).kind === "npc";
}

export function officeAnimStatus(status: AgentStatus): "idle" | "working" | "done" | "waiting" {
  return status === "inactive" ? "idle" : status;
}
