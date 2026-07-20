"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Loader2, Send, Sparkles, Zap } from "lucide-react";

import type { ArchivistTrip } from "@/lib/pixel-office/archivist";
import { resolveOfficeCharacterId, type AgentStatus } from "@/lib/studio-agents";
import type { AgentState } from "./AgentWorkbench";
import { DocumentArchive } from "./DocumentArchive";
import { MessageHub, type HubMessage } from "./MessageHub";
import {
  defaultOfficeAgents,
  PixelOfficeCanvas,
  type InquiryFlowPhase,
} from "./PixelOfficeCanvas";
import { generateResourcesStream } from "@/lib/api";
import {
  consumeBackgroundCreatedResources,
  setBackgroundResourceDraft,
  startBackgroundResourceGeneration,
  useBackgroundResourceOffice
} from "@/lib/background-resource-office";
import { ReActSteps } from "@/components/chat/ReActSteps";
import type { GeneratedResource, ReactStep, ResourceType } from "@/lib/types";

const GENERATE_TYPES: Array<{ id: ResourceType; label: string; icon: string }> = [
  { id: "exercise", label: "练习题", icon: "📝" },
  { id: "note", label: "笔记", icon: "📒" },
  { id: "mindmap", label: "思维导图", icon: "🧠" },
  { id: "video_script", label: "讲解视频", icon: "🎬" },
  { id: "code_lab", label: "实操案例", icon: "💻" },
];

interface ResourceOfficeProps {
  userId: string;
  resources: GeneratedResource[];
  onResourcesAdded: (created: GeneratedResource[]) => void;
  onResourceDeleted: (resourceId: string) => void;
  loading?: boolean;
}

export function ResourceOffice({
  userId,
  resources,
  onResourcesAdded,
  onResourceDeleted,
  loading,
}: ResourceOfficeProps) {
  const [agents, setAgents] = useState<AgentState[]>(defaultOfficeAgents);
  const [messages, setMessages] = useState<HubMessage[]>([]);
  const [hubOpen, setHubOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<ResourceType[]>(["note", "exercise"]);
  const [running, setRunning] = useState(false);
  const [agentReactSteps, setAgentReactSteps] = useState<ReactStep[]>([]);
  const [error, setError] = useState("");
  const [inquiry, setInquiry] = useState<{
    inquiryId: string;
    reason: string;
    questions: string[];
  } | null>(null);
  const [inquiryPhase, setInquiryPhase] = useState<InquiryFlowPhase>(null);
  const [clarification, setClarification] = useState("");
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [showGenerate, setShowGenerate] = useState(false);
  const [activeSpeaker, setActiveSpeaker] = useState<string | null>(null);
  const [archivistTrips, setArchivistTrips] = useState<ArchivistTrip[]>([]);
  const pendingResourcesRef = useRef<GeneratedResource[]>([]);
  /** 按生成顺序记录需拜访的生产 Agent（去重） */
  const archivistAgentIdsRef = useRef<string[]>([]);
  /** 同一次 SSE 流内：inquiry 与 hub_close/done 顺序到达，用 ref 避免误关频道 */
  const inquiryPendingRef = useRef(false);
  const backgroundOffice = useBackgroundResourceOffice(userId);

  useEffect(() => {
    setAgents(backgroundOffice.agents.length ? backgroundOffice.agents : defaultOfficeAgents());
    setMessages(backgroundOffice.messages);
    setHubOpen(backgroundOffice.hubOpen);
    setTopic(backgroundOffice.topic);
    setSelected(backgroundOffice.selected);
    setRunning(backgroundOffice.running);
    setAgentReactSteps(backgroundOffice.agentReactSteps);
    setError(backgroundOffice.error);
    setInquiry(backgroundOffice.inquiry);
    setClarification(backgroundOffice.clarification);
    setShowGenerate(backgroundOffice.showGenerate);
  }, [backgroundOffice]);

  useEffect(() => {
    const created = consumeBackgroundCreatedResources(userId);
    if (created.length > 0) {
      onResourcesAdded(created);
    }
  }, [backgroundOffice.createdResources.length, onResourcesAdded, userId]);

  const bubbles = useMemo(() => {
    const map: Record<string, string> = {};
    for (const msg of messages) {
      if (msg.agent === "user" || msg.kind === "system") continue;
      const id = resolveOfficeCharacterId(msg.agent);
      map[id] = msg.content;
    }
    return map;
  }, [messages]);

  const toggleType = useCallback((id: ResourceType) => {
    setSelected((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      setBackgroundResourceDraft(userId, { selected: next });
      return next;
    });
  }, [userId]);

  const streamHubMessage = useCallback(async (msg: HubMessage) => {
    const content = msg.content || "";
    setMessages((prev) => [...prev, { ...msg, content: "" }]);
    const chunkSize = 10;
    for (let i = 0; i < content.length; i += chunkSize) {
      const delta = content.slice(i, i + chunkSize);
      setMessages((prev) =>
        prev.map((item) => (item.id === msg.id ? { ...item, content: `${item.content}${delta}` } : item))
      );
      await new Promise((resolve) => window.setTimeout(resolve, 20));
    }
  }, []);

  const flushArchivistQueue = useCallback(() => {
    const agentIds = archivistAgentIdsRef.current;
    if (agentIds.length > 0) {
      setAgents((a) =>
        a.map((x) =>
          x.id === "data-archivist" ? { ...x, status: "working" as AgentStatus } : x
        )
      );
      setArchivistTrips([
        {
          id: `archive-${Date.now()}`,
          agentIds: [...agentIds],
        },
      ]);
    }
  }, []);

  const runGeneration = useCallback(
    async (clarify?: string) => {
      if (!topic.trim() || selected.length === 0 || running) return;
      setBackgroundResourceDraft(userId, { topic: topic.trim(), selected, showGenerate: true });
      if (!clarify) {
        setInquiryPhase(null);
        setArchivistTrips([]);
        archivistAgentIdsRef.current = [];
        pendingResourcesRef.current = [];
      }
      await startBackgroundResourceGeneration(userId, clarify);
    },
    [userId, topic, selected, running]
  );

  const handleInquiryArrived = useCallback(() => {
    setInquiryPhase("at_carpet");
  }, []);

  const handleInquiryHome = useCallback(() => {
    setInquiryPhase(null);
    setInquiry(null);
    inquiryPendingRef.current = false;
    setHubOpen(false);
  }, []);

  const handleInquirySubmit = () => {
    if (!clarification.trim()) return;
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        agent: "user",
        role: "用户",
        content: clarification.trim(),
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
    const answer = clarification.trim();
    setClarification("");
    setBackgroundResourceDraft(userId, { clarification: "" });
    inquiryPendingRef.current = false;
    // 立刻收起问询，避免与 background 快照里残留的旧 inquiry 互相覆盖
    setInquiry(null);
    setInquiryPhase("walk_home");
    runGeneration(answer);
  };

  const handleArchivistTripComplete = useCallback((_tripId: string) => {
    archivistAgentIdsRef.current = [];
    setArchivistTrips([]);
    setAgents((a) =>
      a.map((x) =>
        x.id === "data-archivist" ? { ...x, status: "idle" as AgentStatus } : x
      )
    );
  }, []);

  const handleBookshelfClick = useCallback(() => setArchiveOpen(true), []);

  return (
    <div className="resource-office">
      <div className="resource-office-toolbar">
        <div className="resource-office-toolbar-left">
          <Sparkles size={18} />
          <span>学习资源办公室</span>
          {running ? (
            <span className="studio-running-badge">
              <span className="office-live-dot" />
              Agent 协作中
            </span>
          ) : null}
        </div>
        <div className="resource-office-toolbar-actions">
          <button
            type="button"
            className="office-toolbar-btn"
            onClick={() => setArchiveOpen(true)}
          >
            <BookOpen size={16} />
            文档库 ({resources.length})
          </button>
          <button
            type="button"
            className="studio-launch-btn office-toolbar-generate"
            onClick={() => {
              const next = !showGenerate;
              setShowGenerate(next);
              setBackgroundResourceDraft(userId, { showGenerate: next });
            }}
          >
            <Zap size={16} />
            {showGenerate ? "收起派活面板" : "生成资源"}
          </button>
        </div>
      </div>

      <div className="resource-office-body">
        <div className="resource-office-scene">
          <PixelOfficeCanvas
            agents={agents}
            bubbles={bubbles}
            activeSpeaker={activeSpeaker}
            onBookshelfClick={handleBookshelfClick}
            inquiryPhase={inquiryPhase}
            inquiryData={inquiry}
            inquiryDraft={clarification}
            onInquiryDraftChange={(value) => {
              setClarification(value);
              setBackgroundResourceDraft(userId, { clarification: value });
            }}
            onInquirySubmit={handleInquirySubmit}
            onInquiryArrived={handleInquiryArrived}
            onInquiryHome={handleInquiryHome}
            archivistTrips={archivistTrips}
            onArchivistTripComplete={handleArchivistTripComplete}
          />
        </div>

        <aside className="resource-office-sidebar">
          {showGenerate ? (
            <section className="studio-task-section office-sidebar-generate">
              <label className="studio-field-label">学习主题</label>
              <input
                type="text"
                className="studio-topic-input office-topic-input"
                value={topic}
                onChange={(e) => {
                  setTopic(e.target.value);
                  setBackgroundResourceDraft(userId, { topic: e.target.value });
                }}
                placeholder="如：关系代数的选择运算"
                disabled={running}
              />
              <label className="studio-field-label">资源类型</label>
              <div className="studio-type-grid">
                {GENERATE_TYPES.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={`studio-type-tile${selected.includes(t.id) ? " selected" : ""}`}
                    onClick={() => toggleType(t.id)}
                    disabled={running}
                  >
                    <span className="studio-type-icon">{t.icon}</span>
                    <span>{t.label}</span>
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="studio-launch-btn"
                onClick={() => runGeneration()}
                disabled={running || !topic.trim() || selected.length === 0 || !!inquiry}
              >
                {running ? (
                  <>
                    <Loader2 size={16} className="spin" /> 协作生成中…
                  </>
                ) : (
                  <>
                    <Zap size={16} /> 派活给 Agent 团队
                  </>
                )}
              </button>
            </section>
          ) : null}

          {hubOpen || messages.length > 0 ? (
            <MessageHub messages={messages} variant="light" />
          ) : null}

          {agentReactSteps.length > 0 || (running && selected.includes("note")) ? (
            <section className="office-react-panel">
              <ReActSteps
                steps={agentReactSteps}
                loading={running && agentReactSteps.length === 0}
                statusMessage="笔记 Agent ReAct 执行中…"
              />
            </section>
          ) : null}

          {inquiry ? (
            <section className="office-inquiry" aria-label="询问员问询">
              <h4>💬 询问员需要你补充</h4>
              <p>{inquiry.reason}</p>
              <ul>
                {inquiry.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
              <textarea
                className="office-inquiry-input"
                value={clarification}
                onChange={(e) => {
                  setClarification(e.target.value);
                  setBackgroundResourceDraft(userId, { clarification: e.target.value });
                }}
                placeholder="在此回复…"
                disabled={running && inquiryPhase === "walk_home"}
                rows={3}
              />
              <button
                type="button"
                className="studio-launch-btn studio-launch-btn-sm"
                onClick={handleInquirySubmit}
                disabled={!clarification.trim() || inquiryPhase === "walk_to_carpet"}
              >
                <Send size={14} /> 提交补充信息
              </button>
            </section>
          ) : null}

          {error ? <p className="studio-error">{error}</p> : null}
        </aside>
      </div>

      <DocumentArchive
        open={archiveOpen}
        onClose={() => setArchiveOpen(false)}
        resources={resources}
        userId={userId}
        onResourceDeleted={onResourceDeleted}
      />

      {loading ? <div className="office-loading-mask">加载资料中…</div> : null}
    </div>
  );
}
