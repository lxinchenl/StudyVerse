"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";

import type { AgentTrace, ChatRetrieval } from "@/lib/types";

const AGENT_LABELS: Record<string, string> = {
  "main-agent": "主 Agent（ReAct）",
  "retrieval-agent": "检索 Agent",
  "exercise-agent": "练习题 Agent",
  "note-agent": "笔记 Agent",
  "mindmap-agent": "思维导图 Agent",
  "video-agent": "讲解视频 Agent",
  "code-lab-agent": "实操案例 Agent",
  "path-agent": "路径规划 Agent",
  "safety-agent": "安全审校 Agent"
};

export function ChatDiagnostics({
  traces,
  retrieval
}: {
  traces?: AgentTrace[];
  retrieval?: ChatRetrieval;
}) {
  const [open, setOpen] = useState(false);

  if ((!traces || traces.length === 0) && !retrieval) return null;

  return (
    <div className="chat-diagnostics">
      <button type="button" className="chat-diagnostics-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Agent 执行与检索过程
      </button>

      {open ? (
        <div className="chat-diagnostics-body">
          {traces && traces.length > 0 ? (
            <section>
              <h4>专家 Agent 详细轨迹</h4>
              {traces.map((trace, index) => (
                <div key={`${trace.agent}-${index}`} className="trace-item">
                  <strong>
                    <span className={`status-dot ${trace.status}`} />
                    {AGENT_LABELS[trace.agent] ?? trace.agent}
                  </strong>
                  <p className="muted">{trace.summary}</p>
                </div>
              ))}
            </section>
          ) : null}

          {retrieval ? (
            <section>
              <h4>
                <Search size={14} style={{ display: "inline", marginRight: 6 }} />
                RAG 检索结果
              </h4>
              <p className="muted">
                原问题：{retrieval.query || "-"}
              </p>
              <p className="muted">
                改写 queries：
                {retrieval.queries.length > 0 ? retrieval.queries.join(" · ") : "无"}
              </p>
              <p className="muted">
                图谱 entities：
                {retrieval.entities.length > 0 ? retrieval.entities.join(" · ") : "无"}
              </p>
              <p className="muted">
                来源：{retrieval.sourceTypes.length > 0 ? retrieval.sourceTypes.join("、") : "无"}
              </p>
              {retrieval.chunks.length === 0 ? (
                <p className="muted">未命中任何课件片段。</p>
              ) : (
                retrieval.chunks.map((chunk, index) => (
                  <div key={chunk.chunkId ?? index} className="retrieval-hit">
                    <div className="retrieval-hit-head">
                      <strong>【资料{index + 1}】{chunk.title}</strong>
                      {chunk.score != null ? (
                        <span className="tag">score {chunk.score.toFixed(2)}</span>
                      ) : null}
                    </div>
                    {chunk.source ? <p className="muted">{chunk.source}</p> : null}
                    <p className="retrieval-snippet">{chunk.text || "（无文本摘要）"}</p>
                  </div>
                ))
              )}
              {retrieval.kgContext.length > 0 ? (
                <div style={{ marginTop: 10 }}>
                  <strong>图谱关系</strong>
                  {retrieval.kgContext.map((edge, index) => (
                    <p key={index} className="muted">
                      {edge.source} --{edge.relation}--&gt; {edge.target}
                    </p>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
