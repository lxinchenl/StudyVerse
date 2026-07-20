"use client";

import { useEffect, useRef, useState } from "react";

let mermaidReady = false;

/** Soft-sanitize labels so Mermaid 11 mindmap is less likely to throw. */
function softSanitizeMermaid(chart: string): string {
  const lines = chart.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  for (const raw of lines) {
    const line = raw.replace(/\t/g, "  ").replace(/\s+$/, "");
    if (!line.trim()) continue;
    if (line.trim().toLowerCase() === "mindmap") {
      out.push("mindmap");
      continue;
    }
    const match = /^(\s*)(.*)$/.exec(line);
    if (!match) continue;
    let indent = match[1];
    const body = match[2].trim();
    if (indent.length % 2 === 1) indent += " ";

    if (/^root\s*(\(\(|\[|\()/.test(body)) {
      out.push(`${indent}${body}`);
      continue;
    }
    if (/^[A-Za-z_][\w-]*(\(\(.*\)\)|\[.*\]|\(.*\))$/.test(body)) {
      out.push(`${indent}${body}`);
      continue;
    }
    if (
      (body.startsWith('"') && body.endsWith('"')) ||
      !/[()[\]{}<>|&;@\\/#`'"→←⇒⇐↔θΘαβγδμσλ·•…—–:：]/.test(body)
    ) {
      out.push(`${indent}${body}`);
      continue;
    }
    out.push(`${indent}"${body.replace(/"/g, "'")}"`);
  }
  if (!out.length) return "mindmap\n  root((主题))";
  if (out[0].trim().toLowerCase() !== "mindmap") out.unshift("mindmap");
  return out.join("\n");
}

export function MermaidBlock({ chart, className = "mermaid-block" }: { chart: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ref.current || !chart.trim()) return;
    const el = ref.current;
    let cancelled = false;
    setError("");
    el.innerHTML = "";

    const source = softSanitizeMermaid(chart);

    void import("mermaid")
      .then(async ({ default: mermaid }) => {
        if (cancelled) return;
        if (!mermaidReady) {
          mermaid.initialize({
            startOnLoad: false,
            theme: "base",
            securityLevel: "loose",
            // Suppress Mermaid's default "Syntax error in text" DOM dump.
            suppressErrorRendering: true,
            themeVariables: {
              background: "#ffffff",
              primaryColor: "#ede9fe",
              primaryTextColor: "#111827",
              primaryBorderColor: "#8b5cf6",
              secondaryColor: "#dbeafe",
              secondaryTextColor: "#111827",
              secondaryBorderColor: "#60a5fa",
              tertiaryColor: "#dcfce7",
              tertiaryTextColor: "#111827",
              tertiaryBorderColor: "#4ade80",
              lineColor: "#a855f7",
              textColor: "#111827",
              fontFamily:
                "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
              fontSize: "16px"
            }
          });
          mermaidReady = true;
        }

        // Fail fast on bad syntax instead of painting Mermaid's error SVG.
        try {
          await mermaid.parse(source);
        } catch {
          throw new Error("mermaid-parse-failed");
        }

        const id = `mmd-${Math.random().toString(36).slice(2)}`;
        const result = await mermaid.render(id, source);
        if (cancelled || !el) return;
        const svg = result?.svg || "";
        if (!svg || /Syntax error in text/i.test(svg)) {
          throw new Error("mermaid-render-error-svg");
        }
        el.innerHTML = svg;
      })
      .catch(() => {
        if (cancelled) return;
        if (el) el.innerHTML = "";
        setError("思维导图语法有误，已跳过渲染。可在资源库查看原文或重新生成。");
      });

    return () => {
      cancelled = true;
    };
  }, [chart]);

  return (
    <div className={className}>
      <div ref={ref} />
      {error ? <p className="muted" style={{ margin: "8px 0 0", fontSize: 13 }}>{error}</p> : null}
    </div>
  );
}
