"use client";

import { useSyncExternalStore } from "react";

import { generateResourcesStream } from "@/lib/api";
import { resolveOfficeCharacterId, type AgentStatus } from "@/lib/studio-agents";
import type { GeneratedResource, ReactStep, ResourceType } from "@/lib/types";

type HubMessage = {
  id: string;
  agent: string;
  role: string;
  content: string;
  timestamp: string;
  kind?: string;
};

type AgentState = {
  id: string;
  status: AgentStatus;
  role?: string;
};

type InquiryState = {
  inquiryId: string;
  reason: string;
  questions: string[];
} | null;

export type ResourceOfficeSnapshot = {
  userId: string;
  topic: string;
  selected: ResourceType[];
  running: boolean;
  showGenerate: boolean;
  hubOpen: boolean;
  messages: HubMessage[];
  agents: AgentState[];
  agentReactSteps: ReactStep[];
  inquiry: InquiryState;
  clarification: string;
  error: string;
  createdResources: GeneratedResource[];
};

const listeners = new Set<() => void>();
const snapshots = new Map<string, ResourceOfficeSnapshot>();
const STORAGE_PREFIX = "studyverse:bg-resource-office";

function emptySnapshot(userId: string): ResourceOfficeSnapshot {
  return {
    userId,
    topic: "",
    selected: ["note", "exercise"],
    running: false,
    showGenerate: false,
    hubOpen: false,
    messages: [],
    agents: [],
    agentReactSteps: [],
    inquiry: null,
    clarification: "",
    error: "",
    createdResources: []
  };
}

function storageKey(userId: string) {
  return `${STORAGE_PREFIX}:${userId}`;
}

function loadSnapshot(userId: string): ResourceOfficeSnapshot {
  if (typeof window === "undefined") return emptySnapshot(userId);
  try {
    const raw = window.sessionStorage.getItem(storageKey(userId));
    if (!raw) return emptySnapshot(userId);
    const parsed = JSON.parse(raw) as Partial<ResourceOfficeSnapshot>;
    return {
      ...emptySnapshot(userId),
      ...parsed,
      userId,
      running: Boolean(parsed.running)
    };
  } catch {
    return emptySnapshot(userId);
  }
}

function persistSnapshot(snapshot: ResourceOfficeSnapshot) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(storageKey(snapshot.userId), JSON.stringify(snapshot));
}

function getSnapshotFor(userId: string) {
  if (!snapshots.has(userId)) {
    snapshots.set(userId, loadSnapshot(userId));
  }
  return snapshots.get(userId)!;
}

function emit() {
  listeners.forEach((listener) => listener());
}

function updateSnapshot(userId: string, updater: (prev: ResourceOfficeSnapshot) => ResourceOfficeSnapshot) {
  const next = updater(getSnapshotFor(userId));
  snapshots.set(userId, next);
  persistSnapshot(next);
  emit();
}

export function subscribeBackgroundResourceOffice(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getBackgroundResourceOfficeSnapshot(userId?: string | null): ResourceOfficeSnapshot {
  if (!userId) return emptySnapshot("");
  return getSnapshotFor(userId);
}

export function useBackgroundResourceOffice(userId?: string | null) {
  return useSyncExternalStore(
    subscribeBackgroundResourceOffice,
    () => getBackgroundResourceOfficeSnapshot(userId),
    () => getBackgroundResourceOfficeSnapshot(userId)
  );
}

export function setBackgroundResourceDraft(
  userId: string,
  patch: Partial<Pick<ResourceOfficeSnapshot, "topic" | "selected" | "clarification" | "showGenerate">>
) {
  updateSnapshot(userId, (prev) => ({ ...prev, ...patch }));
}

export function consumeBackgroundCreatedResources(userId: string): GeneratedResource[] {
  const created = getSnapshotFor(userId).createdResources;
  if (!created.length) return [];
  updateSnapshot(userId, (prev) => ({ ...prev, createdResources: [] }));
  return created;
}

export async function startBackgroundResourceGeneration(userId: string, clarification?: string) {
  const current = getSnapshotFor(userId);
  const topic = current.topic.trim();
  const selected = current.selected;
  if (!topic || selected.length === 0 || current.running) return;

  updateSnapshot(userId, (prev) => ({
    ...prev,
    running: true,
    error: "",
    showGenerate: true,
    // 用户已提交补充：立刻清掉问询面板，避免旧问题在整轮生成期间一直挂着
    inquiry: null,
    clarification: clarification ? "" : prev.clarification,
    messages: clarification
      ? [
          ...prev.messages,
          {
            id: `user-${Date.now()}`,
            agent: "user",
            role: "用户",
            content: clarification,
            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
          }
        ]
      : [],
    hubOpen: false,
    agentReactSteps: clarification ? prev.agentReactSteps : [],
    createdResources: clarification ? prev.createdResources : []
  }));

  const pendingResources: GeneratedResource[] = [];
  let inquiryPending = false;

  try {
    await generateResourcesStream(
      userId,
      topic,
      selected,
      (event) => {
        if (event.type === "hub_open") {
          updateSnapshot(userId, (prev) => ({ ...prev, hubOpen: true, messages: [] }));
          return;
        }
        if (event.type === "hub_close") {
          updateSnapshot(userId, (prev) => ({ ...prev, hubOpen: inquiryPending }));
          return;
        }
        if (event.type === "agent_status") {
          updateSnapshot(userId, (prev) => ({
            ...prev,
            agents: event.agents.map((a) => ({
              id: resolveOfficeCharacterId(a.id),
              status: a.status as AgentStatus,
              role: a.role
            }))
          }));
          return;
        }
        if (event.type === "hub") {
          updateSnapshot(userId, (prev) => ({
            ...prev,
            messages: [
              ...prev.messages,
              {
                ...event.message,
                agent:
                  event.message.kind === "system"
                    ? "system"
                    : resolveOfficeCharacterId(event.message.agent)
              }
            ]
          }));
          return;
        }
        if (event.type === "inquiry") {
          inquiryPending = true;
          updateSnapshot(userId, (prev) => ({
            ...prev,
            inquiry: {
              inquiryId: event.inquiry_id,
              reason: event.reason,
              questions: event.questions
            },
            running: false,
            hubOpen: true
          }));
          return;
        }
        if (event.type === "agent_progress") {
          updateSnapshot(userId, (prev) => ({
            ...prev,
            agentReactSteps: (event.react_steps ?? []).map((s) => ({
              step: s.step,
              thought: s.thought ?? "",
              action: s.action ?? "",
              expert: s.expert,
              observation: s.observation,
              status: s.status
            }))
          }));
          return;
        }
        if (event.type === "resource_stored") {
          const r = event.resource;
          pendingResources.push(mapGenerated(r));
          return;
        }
        if (event.type === "done") {
          const created = event.resources.map(mapGenerated);
          updateSnapshot(userId, (prev) => ({
            ...prev,
            running: false,
            hubOpen: false,
            inquiry: inquiryPending ? prev.inquiry : null,
            createdResources: [...(created.length ? created : pendingResources), ...prev.createdResources]
          }));
        }
      },
      { clarification }
    );
  } catch (e) {
    updateSnapshot(userId, (prev) => ({
      ...prev,
      running: false,
      error: e instanceof Error ? e.message : "生成失败"
    }));
  } finally {
    updateSnapshot(userId, (prev) => ({ ...prev, running: false }));
  }
}

function mapGenerated(r: {
  id: string;
  type: string;
  title: string;
  summary: string;
  content: string;
  topic: string;
  created_at: string;
  player_url?: string | null;
  scene_count?: number | null;
}): GeneratedResource {
  return {
    id: r.id,
    type: r.type as GeneratedResource["type"],
    title: r.title,
    summary: r.summary,
    content: r.content,
    topic: r.topic,
    createdAt: r.created_at,
    playerUrl: r.player_url ?? undefined,
    sceneCount: r.scene_count ?? undefined
  };
}
