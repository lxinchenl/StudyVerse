"use client";

import { useSyncExternalStore } from "react";

import {
  clearChatHistory,
  clearShortTermMemory,
  fetchChatHistory,
  fetchLLMConfig,
  fetchMainAgentContext,
  fetchProfile,
  mapCourseProposalCard,
  mapMainAgentContext,
  sendChatStream,
  type ChatStreamEvent
} from "@/lib/api";
import { resolveModelLabel } from "@/lib/llm-models";
import type { ChatMessage, MainAgentContext, UserProfile } from "@/lib/types";

type StreamOptions = Parameters<typeof sendChatStream>[3];

type ChatSnapshot = {
  userId: string;
  messages: ChatMessage[];
  profile: UserProfile | null;
  currentModelLabel: string;
  loading: boolean;
  bootstrapping: boolean;
  error: string;
  mainAgentContext: MainAgentContext | null;
};

const listeners = new Set<() => void>();
const snapshots = new Map<string, ChatSnapshot>();
const bootstrappingUsers = new Set<string>();
const STORAGE_PREFIX = "studyverse:bg-chat";

function nowLabel() {
  return new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function emptySnapshot(userId: string): ChatSnapshot {
  return {
    userId,
    messages: [],
    profile: null,
    currentModelLabel: "",
    loading: false,
    bootstrapping: false,
    error: "",
    mainAgentContext: null
  };
}

function storageKey(userId: string) {
  return `${STORAGE_PREFIX}:${userId}`;
}

function loadSnapshot(userId: string): ChatSnapshot {
  if (typeof window === "undefined") return emptySnapshot(userId);
  try {
    const raw = window.sessionStorage.getItem(storageKey(userId));
    if (!raw) return emptySnapshot(userId);
    const parsed = JSON.parse(raw) as Partial<ChatSnapshot>;
    return {
      ...emptySnapshot(userId),
      ...parsed,
      userId,
      loading: Boolean(parsed.loading),
      bootstrapping: false
    };
  } catch {
    return emptySnapshot(userId);
  }
}

function persistSnapshot(snapshot: ChatSnapshot) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(storageKey(snapshot.userId), JSON.stringify(snapshot));
}

function getSnapshotFor(userId: string): ChatSnapshot {
  if (!snapshots.has(userId)) {
    snapshots.set(userId, loadSnapshot(userId));
  }
  return snapshots.get(userId)!;
}

function emit() {
  listeners.forEach((listener) => listener());
}

function updateSnapshot(userId: string, updater: (prev: ChatSnapshot) => ChatSnapshot) {
  const next = updater(getSnapshotFor(userId));
  snapshots.set(userId, next);
  persistSnapshot(next);
  emit();
}

export function subscribeBackgroundChat(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getBackgroundChatSnapshot(userId?: string | null): ChatSnapshot {
  if (!userId) return emptySnapshot("");
  return getSnapshotFor(userId);
}

export function useBackgroundChat(userId?: string | null) {
  return useSyncExternalStore(
    subscribeBackgroundChat,
    () => getBackgroundChatSnapshot(userId),
    () => getBackgroundChatSnapshot(userId)
  );
}

export async function initializeBackgroundChat(userId: string) {
  const current = getSnapshotFor(userId);
  if (current.messages.length || current.bootstrapping || bootstrappingUsers.has(userId)) return;

  bootstrappingUsers.add(userId);
  updateSnapshot(userId, (prev) => ({ ...prev, bootstrapping: true, error: "" }));
  try {
    const [history, profile, llm] = await Promise.all([
      fetchChatHistory(userId),
      fetchProfile(userId),
      fetchLLMConfig()
    ]);
    updateSnapshot(userId, (prev) => ({
      ...prev,
      messages: prev.loading ? prev.messages : history,
      profile,
      currentModelLabel: resolveModelLabel(llm.model, llm.provider),
      bootstrapping: false
    }));
  } catch (e) {
    updateSnapshot(userId, (prev) => ({
      ...prev,
      bootstrapping: false,
      error: e instanceof Error ? e.message : "加载失败"
    }));
  } finally {
    bootstrappingUsers.delete(userId);
  }
}

export async function startBackgroundChat(
  userId: string,
  text: string,
  options?: StreamOptions,
  beforeAppend?: (messages: ChatMessage[]) => ChatMessage[]
) {
  const current = getSnapshotFor(userId);
  if (current.loading) return;

  const pendingId = `pending-${Date.now()}`;
  const userMsg: ChatMessage = {
    id: `user-${Date.now()}`,
    role: "user",
    content: text,
    timestamp: nowLabel()
  };
  const pendingMsg: ChatMessage = {
    id: pendingId,
    role: "assistant",
    content: "",
    timestamp: nowLabel(),
    reactSteps: [],
    streamStatus: "连接推理流…"
  };

  updateSnapshot(userId, (prev) => ({
    ...prev,
    loading: true,
    error: "",
    messages: [...(beforeAppend ? beforeAppend(prev.messages) : prev.messages), userMsg, pendingMsg]
  }));

  try {
    await sendChatStream(userId, text, (event) => {
      applyStreamEvent(userId, pendingId, event);
    }, options);
  } catch (e) {
    updateSnapshot(userId, (prev) => ({
      ...prev,
      messages: prev.messages.filter((m) => m.id !== pendingId && m.id !== userMsg.id),
      error: e instanceof Error ? e.message : "发送失败"
    }));
  } finally {
    updateSnapshot(userId, (prev) => ({ ...prev, loading: false }));
  }
}

export async function clearBackgroundChat(userId: string) {
  const current = getSnapshotFor(userId);
  if (current.loading) return;
  await clearChatHistory(userId);
  updateSnapshot(userId, (prev) => ({ ...prev, messages: [], error: "", mainAgentContext: null }));
}

export async function refreshMainAgentContext(userId: string) {
  try {
    const ctx = await fetchMainAgentContext(userId);
    updateSnapshot(userId, (prev) => ({ ...prev, mainAgentContext: ctx }));
    return ctx;
  } catch {
    return getSnapshotFor(userId).mainAgentContext;
  }
}

export async function clearBackgroundShortTermMemory(userId: string) {
  const current = getSnapshotFor(userId);
  if (current.loading) return;
  await clearShortTermMemory(userId);
  updateSnapshot(userId, (prev) => ({ ...prev, error: "" }));
}

function applyStreamEvent(userId: string, pendingId: string, event: ChatStreamEvent) {
  if (event.type === "status") {
    patchPending(userId, pendingId, { streamStatus: event.message });
    return;
  }

  if (event.type === "answer_start") {
    patchPending(userId, pendingId, { content: "", streamStatus: "模型流式输出中…" });
    return;
  }

  if (event.type === "answer_delta") {
    updateSnapshot(userId, (prev) => ({
      ...prev,
      messages: prev.messages.map((m) =>
        m.id === pendingId
          ? { ...m, content: `${m.content ?? ""}${event.delta}`, streamStatus: "模型流式输出中…" }
          : m
      )
    }));
    return;
  }

  if (event.type === "progress") {
    const mainContext = mapMainAgentContext(event.main_context);
    updateSnapshot(userId, (prev) => ({
      ...prev,
      mainAgentContext: mainContext ?? prev.mainAgentContext,
      messages: prev.messages.map((m) =>
        m.id === pendingId
          ? {
              ...m,
              reactSteps: mapStreamSteps(event.react_steps),
              agentTraces: event.traces?.map((t) => ({
                agent: t.agent,
                role: t.role,
                status: t.status as ChatMessage["agentTraces"] extends (infer U)[] | undefined
                  ? U extends { status: infer S }
                    ? S
                    : never
                  : never,
                summary: t.summary
              })),
              exerciseSets: event.exercise_sets?.map((set) => ({
                resourceId: set.resource_id,
                title: set.title,
                topic: set.topic,
                summary: set.summary,
                questions: (set.questions ?? []).map((q) => ({
                  id: q.id,
                  topic: q.topic,
                  difficulty: q.difficulty,
                  question: q.question,
                  gradingType: q.grading_type ?? "standard",
                  attemptStatus: q.attempt_status,
                  lastScore: q.last_score
                }))
              })),
              mindmaps: event.mindmaps?.map((m) => ({
                resourceId: m.resource_id,
                title: m.title,
                topic: m.topic,
                summary: m.summary,
                mermaidSource: m.mermaid_source
              })),
              notes: event.notes?.map((n) => ({
                resourceId: n.resource_id,
                title: n.title,
                topic: n.topic,
                summary: n.summary,
                markdown: n.markdown
              })),
              codeLabSets: event.code_lab_sets?.map((s) => ({
                resourceId: s.resource_id,
                title: s.title,
                topic: s.topic,
                summary: s.summary,
                challenges: (s.challenges ?? []).map((c) => ({
                  id: c.id,
                  topic: c.topic,
                  difficulty: c.difficulty,
                  question: c.question,
                  starterCode: c.starter_code ?? "",
                  setupCode: c.setup_code ?? "",
                  language: c.language ?? "python",
                  hint: c.hint ?? "",
                  attemptStatus: c.attempt_status,
                  lastScore: c.last_score
                }))
              })),
              courseProposalCard: mapCourseProposalCard(event.course_proposal_card)
            }
          : m
      )
    }));
    return;
  }

  if (event.type === "done") {
    const assistant = event.messages.find((m) => m.role === "assistant");
    if (!assistant) return;
    updateSnapshot(userId, (prev) => ({
      ...prev,
      messages: [
        ...prev.messages.filter((m) => m.id !== pendingId),
        {
          id: assistant.id,
          role: "assistant",
          content: assistant.content,
          timestamp: assistant.timestamp,
          agentTraces: assistant.agent_traces?.map((t) => ({
            agent: t.agent,
            role: t.role,
            status: t.status as ChatMessage["agentTraces"] extends (infer U)[] | undefined
              ? U extends { status: infer S }
                ? S
                : never
              : never,
            summary: t.summary
          })),
          reactSteps: mapStreamSteps(assistant.react_steps),
          retrieval: assistant.retrieval
            ? {
                query: assistant.retrieval.query,
                queries: assistant.retrieval.queries ?? [],
                entities: assistant.retrieval.entities ?? [],
                sourceTypes: assistant.retrieval.source_types ?? [],
                chunks: (assistant.retrieval.chunks ?? []).map((c) => ({
                  chunkId: c.chunk_id,
                  title: c.title ?? "",
                  text: c.text ?? "",
                  source: c.source,
                  score: c.score
                })),
                kgContext: assistant.retrieval.kg_context ?? []
              }
            : undefined,
          explainerVideos: assistant.explainer_videos?.map((v) => ({
            resourceId: v.resource_id,
            title: v.title,
            summary: v.summary,
            playerUrl: v.player_url,
            sceneCount: v.scene_count ?? 0
          })),
          exerciseSets: assistant.exercise_sets?.map((set) => ({
            resourceId: set.resource_id,
            title: set.title,
            topic: set.topic,
            summary: set.summary,
            questions: (set.questions ?? []).map((q) => ({
              id: q.id,
              topic: q.topic,
              difficulty: q.difficulty,
              question: q.question,
              gradingType: q.grading_type ?? "standard",
              attemptStatus: q.attempt_status,
              lastScore: q.last_score
            }))
          })),
          mindmaps: assistant.mindmaps?.map((m) => ({
            resourceId: m.resource_id,
            title: m.title,
            topic: m.topic,
            summary: m.summary,
            mermaidSource: m.mermaid_source
          })),
          notes: assistant.notes?.map((n) => ({
            resourceId: n.resource_id,
            title: n.title,
            topic: n.topic,
            summary: n.summary,
            markdown: n.markdown
          })),
          codeLabSets: assistant.code_lab_sets?.map((s) => ({
            resourceId: s.resource_id,
            title: s.title,
            topic: s.topic,
            summary: s.summary,
            challenges: (s.challenges ?? []).map((c) => ({
              id: c.id,
              topic: c.topic,
              difficulty: c.difficulty,
              question: c.question,
              starterCode: c.starter_code ?? "",
              setupCode: c.setup_code ?? "",
              language: c.language ?? "python",
              hint: c.hint ?? "",
              attemptStatus: c.attempt_status,
              lastScore: c.last_score
            }))
          })),
          courseProposalCard: mapCourseProposalCard(assistant.course_proposal_card)
        }
      ],
      profile: {
        major: event.profile.major,
        course: event.profile.course,
        goal: event.profile.goal,
        recentTopics: event.profile.recent_topics,
        weakPoints: event.profile.weak_points,
        frequentErrors: event.profile.frequent_errors,
        preferences: event.profile.preferences
      }
    }));
  }
}

function patchPending(userId: string, pendingId: string, patch: Partial<ChatMessage>) {
  updateSnapshot(userId, (prev) => ({
    ...prev,
    messages: prev.messages.map((m) => (m.id === pendingId ? { ...m, ...patch } : m))
  }));
}

function mapStreamSteps(
  steps?: Array<{
    step?: number;
    thought?: string;
    action?: string;
    expert?: string;
    tool?: string;
    skill?: string;
    observation?: string;
    status?: string;
    exercise?: { mode?: string; topic?: string };
    code_lab?: { mode?: string; topic?: string };
  }>
) {
  if (!steps?.length) return [];
  return steps.map((s) => ({
    step: s.step,
    thought: s.thought ?? "",
    action: s.action ?? "",
    expert: s.expert,
    tool: s.tool,
    skill: s.skill,
    observation: s.observation,
    status: s.status,
    exercise: s.exercise,
    codeLab: s.code_lab
  }));
}
