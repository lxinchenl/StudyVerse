"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

interface TypingAnimationProps {
  text: string;
  duration?: number;
  deleteDuration?: number;
  holdDuration?: number;
  className?: string;
  loop?: boolean;
  style?: CSSProperties;
}

export function TypingAnimation({
  text,
  duration = 120,
  deleteDuration = 70,
  holdDuration = 1400,
  className,
  loop = true,
  style
}: TypingAnimationProps) {
  const [displayedText, setDisplayedText] = useState<string>("");
  const [phase, setPhase] = useState<"typing" | "holding" | "deleting">("typing");

  useEffect(() => {
    if (!text) return;
    if (!loop && displayedText === text) return;

    let timer: number;

    if (phase === "typing") {
      if (displayedText.length < text.length) {
        timer = window.setTimeout(() => {
          setDisplayedText(text.slice(0, displayedText.length + 1));
        }, duration);
      } else if (loop) {
        timer = window.setTimeout(() => {
          setPhase("deleting");
        }, holdDuration);
      } else {
        setPhase("holding");
      }
    } else if (phase === "deleting") {
      if (displayedText.length > 0) {
        timer = window.setTimeout(() => {
          setDisplayedText(text.slice(0, displayedText.length - 1));
        }, deleteDuration);
      } else {
        setPhase("typing");
      }
    }

    return () => {
      if (timer) window.clearTimeout(timer);
    };
  }, [text, displayedText, phase, duration, deleteDuration, holdDuration, loop]);

  return (
    <h1
      className={cn(
        "m-0 inline-flex items-center gap-1 text-center text-4xl font-bold leading-[1.2] tracking-[-0.02em] drop-shadow-sm",
        className
      )}
      style={style}
    >
      <span>{displayedText}</span>
    </h1>
  );
}
