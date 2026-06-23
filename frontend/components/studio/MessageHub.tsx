"use client";

import { memo, useEffect, useRef } from "react";
import { Radio } from "lucide-react";

import { getAgentMeta, resolveOfficeCharacterId } from "@/lib/studio-agents";
import { BlurInText } from "@/components/ui/blur-in-text";

export interface HubMessage {
  id: string;
  agent: string;
  role: string;
  content: string;
  timestamp: string;
  kind?: string;
}

interface MessageHubProps {
  messages: HubMessage[];
  variant?: "light" | "dark";
}

function HubBubble({ msg, dark }: { msg: HubMessage; dark: boolean }) {
  if (msg.kind === "system") {
    return (
      <div className="studio-hub-msg system">
        <div className="studio-hub-msg-body">
          <BlurInText text={msg.content} />
        </div>
      </div>
    );
  }

  if (msg.kind === "progress") {
    const meta = getAgentMeta(resolveOfficeCharacterId(msg.agent));
    return (
      <div className="studio-hub-msg progress">
        <div className="studio-hub-msg-meta">
          {meta.name} · {msg.timestamp}
        </div>
        <div className="studio-hub-msg-body">
          <BlurInText text={msg.content} />
        </div>
      </div>
    );
  }

  const isUser = msg.agent === "user";
  const meta = isUser ? null : getAgentMeta(resolveOfficeCharacterId(msg.agent));

  return (
    <div className={`studio-hub-msg${isUser ? " user" : ""}${dark ? " dark" : ""}`}>
      <div
        className="studio-hub-msg-avatar"
        style={
          isUser
            ? { background: dark ? "#1a3a6e" : "#E8F3FF", color: dark ? "#6eb5ff" : "#0052D9" }
            : { background: `${meta!.color}${dark ? "33" : "18"}`, color: meta!.color }
        }
      >
        {isUser ? "👤" : meta!.emoji}
      </div>
      <div>
        <div className="studio-hub-msg-meta">
          {isUser ? "你" : meta!.name} · {msg.timestamp}
        </div>
        <div className="studio-hub-msg-body">
          {isUser ? msg.content : <BlurInText text={msg.content} />}
        </div>
      </div>
    </div>
  );
}

function MessageHubInner({ messages, variant = "light" }: MessageHubProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const dark = variant === "dark";

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className={`studio-hub${dark ? " studio-hub-dark" : ""}`}>
      <div className="studio-hub-header">
        <Radio size={14} className={runningDot(messages)} />
        MsgHub · 协作频道
      </div>
      <div className="studio-hub-messages">
        {messages.length === 0 ? (
          <div className="studio-hub-empty">
            <p>派活后，Agent 会在这里实时汇报进度</p>
          </div>
        ) : (
          messages.map((msg) => <HubBubble key={msg.id} msg={msg} dark={dark} />)
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

function runningDot(messages: HubMessage[]): string {
  return messages.length > 0 ? "studio-hub-live" : "";
}

export const MessageHub = memo(MessageHubInner);
