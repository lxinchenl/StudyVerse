"use client";

import { useCallback, useMemo, useState } from "react";
import { Loader2, Send, Sparkles, X, Zap } from "lucide-react";

import type { AgentStatus } from "@/lib/studio-agents";
import type { AgentState } from "./AgentWorkbench";
import { MessageHub, type HubMessage } from "./MessageHub";
import { VirtualOffice } from "./VirtualOffice";
import { generateResourcesStream } from "@/lib/api";
import type { GeneratedResource, ResourceType } from "@/lib/types";

const GENERATE_TYPES: Array<{ id: ResourceType; label: string; icon: string }> = [
  { id: "exercise", label: "练习题", icon: "📝" },
  { id: "note", label: "笔记", icon: "📒" },
  { id: "mindmap", label: "思维导图", icon: "🧠" },
  { id: "video_script", label: "讲解视频", icon: "🎬" },
  { id: "code_lab", label: "实操案例", icon: "💻" },
];

interface ResourceStudioProps {
  userId: string;
  open: boolean;
  onClose: () => void;
  onComplete: (resources: GeneratedResource[]) => void;
  initialTopic?: string;
  initialTypes?: ResourceType[];
}

export function ResourceStudio({
  userId,
  open,
  onClose,
  onComplete,
  initialTopic = "",
  initialTypes = ["note", "exercise"],
}: ResourceStudioProps) {
  const [topic, setTopic] = useState(initialTopic);
  const [selected, setSelected] = useState<ResourceType[]>(initialTypes);
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [messages, setMessages] = useState<HubMessage[]>([]);
  const [inquiry, setInquiry] = useState<{
    inquiryId: string;
    reason: string;
    questions: string[];
  } | null>(null);
  const [clarification, setClarification] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const latestBubbles = useMemo(() => {
    const bubbles: Record<string, string> = {};
    for (const msg of messages) {
      if (msg.agent !== "user" && msg.kind !== "system") {
        bubbles[msg.agent] = msg.content.length > 36 ? `${msg.content.slice(0, 36)}…` : msg.content;
      }
    }
    return bubbles;
  }, [messages]);

  const toggleType = useCallback((id: ResourceType) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

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

  const runGeneration = useCallback(
    async (clarify?: string) => {
      if (!topic.trim() || selected.length === 0 || running) return;
      setRunning(true);
      setError("");
      if (!clarify) {
        setInquiry(null);
        setMessages([]);
        setAgents([]);
      }

      try {
        await generateResourcesStream(
          userId,
          topic.trim(),
          selected,
          (event) => {
            if (event.type === "agent_status") {
              setAgents(
                event.agents.map((a) => ({
                  id: a.id,
                  status: a.status as AgentStatus,
                  role: a.role,
                }))
              );
            } else if (event.type === "hub") {
              void streamHubMessage(event.message);
            } else if (event.type === "inquiry") {
              setInquiry({
                inquiryId: event.inquiry_id,
                reason: event.reason,
                questions: event.questions,
              });
            } else if (event.type === "done") {
              const created = event.resources.map((r) => ({
                id: r.id,
                type: r.type as GeneratedResource["type"],
                title: r.title,
                summary: r.summary,
                content: r.content,
                topic: r.topic,
                createdAt: r.created_at,
                playerUrl: r.player_url ?? undefined,
                sceneCount: r.scene_count ?? undefined,
              }));
              if (created.length > 0) onComplete(created);
              setInquiry(null);
            }
          },
          { clarification: clarify }
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "生成失败");
      } finally {
        setRunning(false);
      }
    },
    [userId, topic, selected, running, onComplete, streamHubMessage]
  );

  const handleStart = () => runGeneration();
  const handleClarify = () => {
    if (!clarification.trim()) return;
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        agent: "user",
        role: "用户",
        content: clarification.trim(),
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        kind: "speak",
      },
    ]);
    const answer = clarification.trim();
    setClarification("");
    runGeneration(answer);
  };

  if (!open) return null;

  return (
    <div
      className="studio-overlay"
      onClick={(e) => e.target === e.currentTarget && !running && onClose()}
    >
      <div className="studio-panel studio-panel-marvis" role="dialog" aria-label="资源工作室">
        <header className="studio-header studio-header-dark">
          <div className="studio-header-brand">
            <div className="studio-logo">
              <Sparkles size={18} />
            </div>
            <div>
              <h2>资源工作室</h2>
              <p>多 Agent 协作 · MsgHub 实时频道</p>
            </div>
          </div>
          <div className="studio-header-actions">
            {running ? (
              <span className="studio-running-badge">
                <span className="office-live-dot" />
                团队协作中
              </span>
            ) : null}
            <button type="button" className="studio-close-btn" onClick={onClose} disabled={running} aria-label="关闭">
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="studio-marvis-body">
          {/* 左侧：马维斯式对话 + 任务配置 */}
          <aside className="studio-left-panel">
            <section className="studio-task-section">
              <label className="studio-field-label">学习主题</label>
              <input
                type="text"
                className="studio-topic-input studio-topic-input-dark"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="如：关系代数的选择运算"
                disabled={running}
                onKeyDown={(e) => e.key === "Enter" && !inquiry && handleStart()}
              />

              <label className="studio-field-label">生成资源类型</label>
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
                onClick={handleStart}
                disabled={running || !topic.trim() || selected.length === 0 || !!inquiry}
              >
                {running ? (
                  <>
                    <Loader2 size={18} className="spin" /> 协作生成中…
                  </>
                ) : (
                  <>
                    <Zap size={18} /> 派活给 Agent 团队
                  </>
                )}
              </button>
            </section>

            <MessageHub messages={messages} variant="dark" />

            {inquiry ? (
              <div className="studio-inquiry studio-inquiry-dark">
                <h4>💬 询问 Agent 需要补充</h4>
                <p>{inquiry.reason}</p>
                <ul>
                  {inquiry.questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
                <textarea
                  className="studio-inquiry-input studio-inquiry-input-dark"
                  value={clarification}
                  onChange={(e) => setClarification(e.target.value)}
                  placeholder="补充细节后提交…"
                />
                <button
                  type="button"
                  className="studio-launch-btn studio-launch-btn-sm"
                  onClick={handleClarify}
                  disabled={!clarification.trim() || running}
                >
                  <Send size={16} /> 提交并继续
                </button>
              </div>
            ) : null}

            {error ? <p className="studio-error">{error}</p> : null}
          </aside>

          {/* 右侧：虚拟办公室 */}
          <main className="studio-right-panel">
            <VirtualOffice agents={agents} latestBubbles={latestBubbles} running={running} />
          </main>
        </div>
      </div>
    </div>
  );
}
