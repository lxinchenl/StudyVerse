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
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
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
