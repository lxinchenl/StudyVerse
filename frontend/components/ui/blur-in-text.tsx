"use client";

import { useMemo } from "react";

import { cn } from "@/lib/utils";

interface BlurInTextProps {
  text: string;
  className?: string;
}

/**
 * Lightweight "Blur In by Text" rendering:
 * each character fades from blur to sharp with staggered delay.
 */
export function BlurInText({ text, className }: BlurInTextProps) {
  const chars = useMemo(() => Array.from(text), [text]);

  return (
    <span className={cn("blur-in-text", className)} aria-live="polite">
      {chars.map((ch, i) => (
        <span
          key={`${ch}-${i}`}
          className="blur-in-text-char"
          style={{ animationDelay: `${Math.min(i * 0.008, 0.36)}s` }}
        >
          {ch}
        </span>
      ))}
    </span>
  );
}
