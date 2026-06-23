"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import rehypeRaw from "rehype-raw";
import { MermaidBlock } from "@/components/mermaid/MermaidBlock";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";

function MermaidBlockWrapper({ chart }: { chart: string }) {
  return <MermaidBlock chart={chart} />;
}

export function MarkdownRenderer({
  content,
  variant = "default"
}: {
  content: string;
  variant?: "default" | "note";
}) {
  const bodyClass =
    variant === "note" ? "markdown-body markdown-body-note" : "markdown-body";
  const rehypePlugins =
    variant === "note"
      ? [rehypeRaw, rehypeKatex, rehypeHighlight]
      : [rehypeKatex, rehypeHighlight];

  return (
    <div className={bodyClass}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={rehypePlugins}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const lang = match?.[1];
            const text = String(children).replace(/\n$/, "");
            if (lang === "mermaid") {
              return <MermaidBlockWrapper chart={text} />;
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          img({ src, alt, ...props }) {
            return (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={src}
                alt={alt ?? ""}
                className="note-inline-image"
                loading="lazy"
                {...props}
              />
            );
          },
          table({ children }) {
            return (
              <div className="md-table-wrap">
                <table>{children}</table>
              </div>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
