"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Eraser, MessageSquare, Trash2 } from "lucide-react";

import { ChatDiagnostics } from "@/components/chat/ChatDiagnostics";
import { CourseProposalCard, proposalCardToApi } from "@/components/chat/CourseProposalCard";
import { ReActSteps } from "@/components/chat/ReActSteps";
import { ExplainerVideoPlayer } from "@/components/explainer/ExplainerVideoPlayer";
import { AppShell } from "@/components/layout/AppShell";
import { ChatPromptInput } from "@/components/ui/animated-ai-input";
import { BlurInText } from "@/components/ui/blur-in-text";
import {
  CodeLabPanel,
  ExercisePanel,
  MarkdownRenderer,
  MindmapViewer,
  NoteViewer
} from "@/lib/lazy-components";
import { useAuth } from "@/lib/auth";
import {
  clearChatHistory,
  clearShortTermMemory,
  fetchChatHistory,
  fetchLLMConfig,
  fetchProfile,
  mapCourseProposalCard,
  sendChatStream,
  uploadUserFile,
  type ChatStreamEvent
} from "@/lib/api";
import { resolveModelLabel } from "@/lib/llm-models";
import type { ChatMessage, CourseProposalCard as CourseProposalCardType, UserProfile } from "@/lib/types";

function nowLabel() {
  return new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function ProfileField({
  label,
  children
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="profile-field">
      <span className="profile-field-label">{label}</span>
      <div className="profile-field-body">{children}</div>
    </div>
  );
}

function ProfileTags({
  items,
  empty = "暂无",
  tone = "default"
}: {
  items?: string[];
  empty?: string;
  tone?: "default" | "warn" | "danger";
}) {
  if (!items?.length) {
    return <p className="profile-field-empty">{empty}</p>;
  }
  return (
    <ul className="profile-tag-list">
      {items.map((item, index) => (
        <li
          key={`${item}-${index}`}
          className={tone === "default" ? "profile-tag" : `profile-tag profile-tag--${tone}`}
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

function mapStreamTraces(
  traces?: Array<{ agent: string; role: string; summary: string; status: string }>
) {
  return traces?.map((t) => ({
    agent: t.agent,
    role: t.role,
    status: t.status as ChatMessage["agentTraces"] extends (infer U)[] | undefined
      ? U extends { status: infer S }
        ? S
        : never
      : never,
    summary: t.summary
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

export default function LearnPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentModelLabel, setCurrentModelLabel] = useState("");
  const [fileUploading, setFileUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) return;
    Promise.all([fetchChatHistory(user.id), fetchProfile(user.id), fetchLLMConfig()])
      .then(([history, prof, llm]) => {
        setMessages(history);
        setProfile(prof);
        setCurrentModelLabel(resolveModelLabel(llm.model, llm.provider));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, [user]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function applyStreamEvent(pendingId: string, event: ChatStreamEvent) {
    if (event.type === "status") {
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingId ? { ...m, streamStatus: event.message } : m))
      );
      return;
    }

    if (event.type === "answer_start") {
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingId ? { ...m, content: "", streamStatus: "模型流式输出中…" } : m))
      );
      return;
    }

    if (event.type === "answer_delta") {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                ...m,
                content: `${m.content ?? ""}${event.delta}`,
                streamStatus: "模型流式输出中…"
              }
            : m
        )
      );
      return;
    }

    if (event.type === "progress") {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                ...m,
                reactSteps: mapStreamSteps(event.react_steps),
                agentTraces: mapStreamTraces(event.traces),
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
      );
      return;
    }

    if (event.type === "done") {
      const assistant = event.messages.find((m) => m.role === "assistant");
      if (!assistant) return;
      setMessages((prev) => {
        const kept = prev.filter((m) => m.id !== pendingId);
        return [
          ...kept,
          {
            id: assistant.id,
            role: "assistant",
            content: assistant.content,
            timestamp: assistant.timestamp,
            agentTraces: mapStreamTraces(assistant.agent_traces),
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
        ];
      });
      setProfile({
        major: event.profile.major,
        course: event.profile.course,
        goal: event.profile.goal,
        recentTopics: event.profile.recent_topics,
        weakPoints: event.profile.weak_points,
        frequentErrors: event.profile.frequent_errors,
        preferences: event.profile.preferences
      });
    }
  }

  async function handleClearChat() {
    if (!user || loading) return;
    if (!window.confirm("确定清空当前对话记录？界面与已保存的对话历史将被删除，资源库不受影响。")) return;
    setError("");
    try {
      await clearChatHistory(user.id);
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "清空对话失败");
    }
  }

  async function handleClearMemory() {
    if (!user || loading) return;
    if (
      !window.confirm(
        "确定清空短期记忆？将重置工作台推理缓存与事件记忆片段；对话记录、用户画像与资源库不受影响。"
      )
    ) {
      return;
    }
    setError("");
    try {
      await clearShortTermMemory(user.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "清空记忆失败");
    }
  }

  async function handleProposalAction(card: CourseProposalCardType, action: "confirm" | "cancel") {
    if (!user || loading) return;

    const label = action === "confirm" ? "确认生成定制系统课" : "取消定制系统课";
    const pendingId = `pending-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: label,
      timestamp: nowLabel()
    };
    const pendingMsg: ChatMessage = {
      id: pendingId,
      role: "assistant",
      content: "",
      timestamp: nowLabel(),
      reactSteps: [],
      streamStatus: action === "confirm" ? "正在生成定制系统课…" : "处理中…"
    };

    setMessages((prev) =>
      prev.map((m) =>
        m.courseProposalCard?.kind === "course_proposal" &&
        m.courseProposalCard.status === "pending" &&
        m.courseProposalCard.courseTitle === card.courseTitle
          ? {
              ...m,
              courseProposalCard: {
                ...m.courseProposalCard,
                status: action === "confirm" ? ("confirmed" as const) : ("cancelled" as const)
              }
            }
          : m
      ).concat(userMsg, pendingMsg)
    );
    setError("");
    setLoading(true);

    try {
      await sendChatStream(
        user.id,
        label,
        (event) => applyStreamEvent(pendingId, event),
        {
          courseWorkflowAction: action,
          courseProposal: proposalCardToApi(card)
        }
      );
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== pendingId && m.id !== userMsg.id));
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!user || !text || loading) return;

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

    setInput("");
    setError("");
    setLoading(true);
    setMessages((prev) => [...prev, userMsg, pendingMsg]);

    try {
      await sendChatStream(user.id, text, (event) => {
        applyStreamEvent(pendingId, event);
      });
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== pendingId && m.id !== userMsg.id));
      setInput(text);
      setError(e instanceof Error ? e.message : "发送失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleFileSelect(files: FileList) {
    if (!user || !files.length) return;
    setFileUploading(true);
    setUploadNotice("");
    setError("");
    try {
      const saved: string[] = [];
      for (const file of Array.from(files)) {
        const result = await uploadUserFile(user.id, file);
        saved.push(result.filename);
      }
      setUploadNotice(
        saved.length === 1 ? `已保存文件：${saved[0]}` : `已保存 ${saved.length} 个文件`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "文件上传失败");
    } finally {
      setFileUploading(false);
    }
  }

  return (
    <AppShell
      fillHeight
      title="多 Agent 学习"
      subtitle={`当前用户 ${user?.name} · 主 Agent ReAct 实时推理流`}
    >
      <div className="learn-page">
        {error ? <p className="muted learn-page-error">{error}</p> : null}
        <div className="chat-layout">
        <div className="chat-panel">
          <div className="chat-toolbar">
            <div className="chat-toolbar-left">
              <MessageSquare size={16} className="chat-toolbar-icon" />
              <span className="chat-toolbar-title">多 Agent 对话</span>
              {currentModelLabel ? (
                <span className="chat-model-badge">{currentModelLabel}</span>
              ) : null}
            </div>
            <div className="chat-toolbar-actions">
              <button
                type="button"
                className="btn-secondary chat-toolbar-btn"
                onClick={handleClearChat}
                disabled={loading || messages.length === 0}
              >
                <Trash2 size={14} />
                清空对话
              </button>
              <button
                type="button"
                className="btn-secondary chat-toolbar-btn"
                onClick={handleClearMemory}
                disabled={loading}
              >
                <Eraser size={14} />
                清空短期记忆
              </button>
            </div>
          </div>
          <div className="chat-messages">
            {messages.map((msg) => (
                <div key={msg.id} className="chat-message-block">
                  <div
                    className={
                      msg.role === "user"
                        ? "msg user"
                        : msg.id.startsWith("pending-")
                          ? "msg assistant msg-pending"
                          : "msg assistant"
                    }
                  >
                    {msg.role === "assistant" ? (
                      msg.id.startsWith("pending-") ? (
                        <>
                          <ReActSteps
                            steps={msg.reactSteps}
                            traces={msg.agentTraces}
                            loading={!msg.reactSteps?.length}
                            statusMessage={msg.streamStatus}
                          />
                          {msg.reactSteps?.length ? (
                            <p className="typing-line">
                              <span className="status-dot running" />
                              <span className="typing-indicator">{msg.streamStatus ?? "推理中"}</span>
                            </p>
                          ) : null}
                          {msg.content ? (
                            <p className="chat-streaming-text">
                              <BlurInText text={msg.content} />
                            </p>
                          ) : null}
                        </>
                      ) : (
                        <>
                          <ReActSteps steps={msg.reactSteps} traces={msg.agentTraces} />
                          {msg.content ? (
                            <>
                              {msg.reactSteps?.length ? <hr className="react-answer-divider" /> : null}
                              <MarkdownRenderer content={msg.content} />
                            </>
                          ) : null}
                        </>
                      )
                    ) : (
                      msg.content
                    )}
                  </div>
                  {msg.role === "assistant" ? (
                    <>
                      {msg.courseProposalCard ? (
                        <CourseProposalCard
                          card={msg.courseProposalCard}
                          disabled={loading}
                          onConfirm={(card) => handleProposalAction(card, "confirm")}
                          onCancel={(card) => handleProposalAction(card, "cancel")}
                        />
                      ) : null}
                      {msg.exerciseSets?.map((set) => (
                        <ExercisePanel
                          key={set.resourceId}
                          exerciseSet={set}
                          userId={user?.id ?? ""}
                          compact
                        />
                      ))}
                      {msg.mindmaps?.map((mindmap) => (
                        <MindmapViewer key={mindmap.resourceId} mindmap={mindmap} compact />
                      ))}
                      {msg.notes?.map((note) => (
                        <NoteViewer key={note.resourceId} note={note} compact />
                      ))}
                      {msg.codeLabSets?.map((lab) => (
                        <CodeLabPanel key={lab.resourceId} labSet={lab} userId={user?.id ?? ""} compact />
                      ))}
                      {!msg.id.startsWith("pending-") ? (
                        <>
                          {msg.explainerVideos?.map((video) => (
                            <ExplainerVideoPlayer key={video.resourceId} video={video} compact />
                          ))}
                          <ChatDiagnostics traces={msg.agentTraces} retrieval={msg.retrieval} />
                        </>
                      ) : null}
                    </>
                  ) : null}
                </div>
              ))}
            <div ref={messagesEndRef} />
          </div>
          <div className="chat-input-area">
            {uploadNotice ? <p className="chat-upload-notice">{uploadNotice}</p> : null}
            <ChatPromptInput
              value={input}
              onChange={setInput}
              onSubmit={() => void handleSend()}
              loading={loading}
              fileUploading={fileUploading}
              onFileSelect={handleFileSelect}
              onModelChange={(modelId, provider) => {
                setCurrentModelLabel(resolveModelLabel(modelId, provider));
              }}
            />
          </div>
        </div>
        <aside className="chat-sidebar profile-sidebar">
          <h3 className="profile-sidebar-title">用户画像</h3>
          <div className="profile-sidebar-body">
            <ProfileField label="用户">
              <p className="profile-field-value">
                {user?.name ?? "—"}
                {user?.id ? <span className="profile-field-meta">（{user.id}）</span> : null}
              </p>
            </ProfileField>
            {profile?.course ? (
              <ProfileField label="课程">
                <p className="profile-field-value">{profile.course}</p>
              </ProfileField>
            ) : null}
            {profile?.goal ? (
              <ProfileField label="目标">
                <p className="profile-field-value">{profile.goal}</p>
              </ProfileField>
            ) : null}
            <ProfileField label="近期主题">
              <ProfileTags items={profile?.recentTopics} empty="暂无学习记录" />
            </ProfileField>
            <ProfileField label="薄弱点">
              <ProfileTags items={profile?.weakPoints} empty="暂无标记" tone="warn" />
            </ProfileField>
            <ProfileField label="练习常错">
              <ProfileTags items={profile?.frequentErrors} empty="暂无记录" tone="danger" />
            </ProfileField>
          </div>
        </aside>
        </div>
      </div>
    </AppShell>
  );
}
