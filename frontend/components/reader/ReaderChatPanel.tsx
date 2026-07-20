"use client";

import { useEffect, useRef, useState } from "react";
import { GripHorizontal, MessageCircle, X } from "lucide-react";

import { CourseProposalCard, proposalCardToApi } from "@/components/chat/CourseProposalCard";
import { ReActSteps } from "@/components/chat/ReActSteps";
import { ChatPromptInput } from "@/components/ui/animated-ai-input";
import { BlurInText } from "@/components/ui/blur-in-text";
import { MarkdownRenderer } from "@/lib/lazy-components";
import {
  initializeBackgroundChat,
  startBackgroundChat,
  useBackgroundChat
} from "@/lib/background-chat";
import { resolveModelLabel } from "@/lib/llm-models";
import type { ChatMessage, CourseProposalCard as CourseProposalCardType } from "@/lib/types";

type ReaderChatPanelProps = {
  open: boolean;
  onClose: () => void;
  userId: string;
  courseId: string;
  documentId: string;
  documentTitle: string;
};

const MIN_WIDTH = 380;
const MIN_HEIGHT = 460;
const DEFAULT_WIDTH = 440;
const DEFAULT_HEIGHT = 620;

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

export function ReaderChatPanel({
  open,
  onClose,
  userId,
  courseId,
  documentId,
  documentTitle
}: ReaderChatPanelProps) {
  const chat = useBackgroundChat(userId);
  const [input, setInput] = useState("");
  const [size, setSize] = useState({ width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef(false);
  const resizeStartRef = useRef({ x: 0, y: 0, width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT });

  useEffect(() => {
    if (!open || !userId) return;
    void initializeBackgroundChat(userId);
  }, [open, userId]);

  useEffect(() => {
    if (!open) return;
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat.messages, chat.loading, open]);

  useEffect(() => {
    function onMouseMove(event: MouseEvent) {
      if (!resizingRef.current) return;
      const dx = event.clientX - resizeStartRef.current.x;
      const dy = event.clientY - resizeStartRef.current.y;
      const maxWidth = Math.min(window.innerWidth - 32, 760);
      const maxHeight = Math.min(window.innerHeight - 32, 900);
      setSize({
        width: Math.max(MIN_WIDTH, Math.min(maxWidth, resizeStartRef.current.width + dx)),
        height: Math.max(MIN_HEIGHT, Math.min(maxHeight, resizeStartRef.current.height + dy))
      });
    }

    function onMouseUp() {
      resizingRef.current = false;
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  if (!open) return null;

  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text || chat.loading) return;
    setInput("");
    await startBackgroundChat(userId, text, {
      courseId,
      documentId
    });
  }

  async function handleProposalAction(card: CourseProposalCardType, action: "confirm" | "cancel") {
    if (chat.loading) return;
    const label = action === "confirm" ? "确认生成定制系统课" : "取消定制系统课";
    await startBackgroundChat(
      userId,
      label,
      {
        courseId,
        documentId,
        courseWorkflowAction: action,
        courseProposal: proposalCardToApi(card)
      },
      (prev) =>
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
        )
    );
  }

  function startResize(event: React.MouseEvent<HTMLDivElement>) {
    event.preventDefault();
    resizingRef.current = true;
    resizeStartRef.current = {
      x: event.clientX,
      y: event.clientY,
      width: size.width,
      height: size.height
    };
  }

  return (
    <div className="reader-chat-panel" style={{ width: size.width, height: size.height }}>
      <div className="reader-chat-header">
        <div className="reader-chat-header-main">
          <MessageCircle size={18} />
          <div className="reader-chat-header-text">
            <strong>向 Agent 提问</strong>
            <span className="muted">{documentTitle}</span>
          </div>
        </div>
        <button type="button" className="reader-chat-close" onClick={onClose} aria-label="关闭">
          <X size={18} />
        </button>
      </div>

      {chat.error ? <p className="reader-chat-error">{chat.error}</p> : null}

      <div className="reader-chat-messages">
        {chat.messages.length === 0 ? (
          <p className="muted reader-chat-empty">与聊天页共享同一会话；在此提问后，切换到「多 Agent 学习」也能看到记录。</p>
        ) : (
          chat.messages.map((msg) => (
            <ReaderChatMessage
              key={msg.id}
              msg={msg}
              loading={chat.loading}
              onProposalAction={handleProposalAction}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="reader-chat-input">
        <ChatPromptInput
          value={input}
          onChange={setInput}
          onSubmit={() => void handleSend()}
          loading={chat.loading || chat.bootstrapping}
          placeholder="针对选段或全文提问…"
          onModelChange={(modelId, provider) => {
            void modelId;
            void resolveModelLabel(modelId, provider);
          }}
        />
      </div>

      <div
        className="reader-chat-resize"
        onMouseDown={startResize}
        role="presentation"
        aria-hidden
      >
        <GripHorizontal size={16} />
      </div>
    </div>
  );
}

function ReaderChatMessage({
  msg,
  loading,
  onProposalAction
}: {
  msg: ChatMessage;
  loading: boolean;
  onProposalAction: (card: CourseProposalCardType, action: "confirm" | "cancel") => void;
}) {
  const isPending = msg.id.startsWith("pending-");

  return (
    <div className="reader-chat-message-block">
      <div className={msg.role === "user" ? "msg user" : isPending ? "msg assistant msg-pending" : "msg assistant"}>
        {msg.role === "assistant" ? (
          isPending ? (
            <>
              <ReActSteps
                steps={mapStreamSteps(msg.reactSteps)}
                traces={msg.agentTraces}
                loading={!msg.reactSteps?.length}
                statusMessage={msg.streamStatus}
              />
              {msg.content ? (
                <p className="chat-streaming-text">
                  <BlurInText text={msg.content} />
                </p>
              ) : null}
            </>
          ) : (
            <>
              <ReActSteps steps={mapStreamSteps(msg.reactSteps)} traces={msg.agentTraces} />
              {msg.content ? <MarkdownRenderer content={msg.content} /> : null}
            </>
          )
        ) : (
          msg.content
        )}
      </div>
      {msg.courseProposalCard ? (
        <CourseProposalCard
          card={msg.courseProposalCard}
          disabled={loading}
          onConfirm={(card) => onProposalAction(card, "confirm")}
          onCancel={(card) => onProposalAction(card, "cancel")}
        />
      ) : null}
    </div>
  );
}
