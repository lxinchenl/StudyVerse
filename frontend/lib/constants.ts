export const DOC_TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  pptx: "PPT",
  docx: "Word",
  markdown: "Markdown",
  txt: "文本",
  code: "代码"
};

/** Browser uses same-origin /api via nginx; SSR/build falls back to localhost. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  (typeof window !== "undefined" ? "/api" : "http://localhost:8000/api");

export function fileDownloadUrl(fileUrl: string | undefined): string | null {
  if (!fileUrl) return null;
  if (fileUrl.startsWith("http")) return fileUrl;
  const base = API_BASE.replace(/\/api$/, "");
  return `${base}${fileUrl}`;
}

/** Rewrite relative note image paths to backend asset URLs. */
export function rewriteNoteMarkdown(markdown: string, resourceId: string): string {
  const origin = API_BASE.replace(/\/api$/, "");
  return markdown.replace(
    /\]\(images\/([^)]+)\)/g,
    (_, file) =>
      `](${origin}/api/note/assets/${resourceId}/${encodeURIComponent(file)})`
  );
}
