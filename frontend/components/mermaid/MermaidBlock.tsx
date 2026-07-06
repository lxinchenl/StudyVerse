"use client";

import { useEffect, useRef } from "react";

let mermaidReady = false;

export function MermaidBlock({ chart, className = "mermaid-block" }: { chart: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !chart.trim()) return;
    const el = ref.current;
    let cancelled = false;

    void import("mermaid").then(({ default: mermaid }) => {
      if (cancelled) return;
      if (!mermaidReady) {
        mermaid.initialize({
          startOnLoad: false,
          theme: "base",
          securityLevel: "loose",
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
            fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            fontSize: "16px"
          }
        });
        mermaidReady = true;
      }
      const id = `mmd-${Math.random().toString(36).slice(2)}`;
      return mermaid.render(id, chart);
    }).then((result) => {
      if (!cancelled && result && el) el.innerHTML = result.svg;
    }).catch(() => {
      if (!cancelled && el) {
        el.textContent = "思维导图渲染失败，请检查 Mermaid 语法。";
      }
    });

    return () => {
      cancelled = true;
    };
  }, [chart]);

  return <div ref={ref} className={className} />;
}
