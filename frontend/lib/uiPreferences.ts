export type ChatFontSize = "sm" | "md" | "lg" | "xl";

export const CHAT_FONT_SIZE_OPTIONS: Array<{ value: ChatFontSize; label: string; px: number }> = [
  { value: "sm", label: "小", px: 13 },
  { value: "md", label: "标准", px: 15 },
  { value: "lg", label: "大", px: 17 },
  { value: "xl", label: "特大", px: 19 }
];

const STORAGE_KEY = "edu_agent_chat_font_size";
export const CHAT_FONT_SIZE_EVENT = "edu-agent:chat-font-size-changed";

const DEFAULT_SIZE: ChatFontSize = "md";

function isChatFontSize(value: string | null | undefined): value is ChatFontSize {
  return value === "sm" || value === "md" || value === "lg" || value === "xl";
}

export function getChatFontSize(): ChatFontSize {
  if (typeof window === "undefined") return DEFAULT_SIZE;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isChatFontSize(stored) ? stored : DEFAULT_SIZE;
}

export function getChatFontSizePx(size: ChatFontSize = getChatFontSize()): number {
  return CHAT_FONT_SIZE_OPTIONS.find((item) => item.value === size)?.px ?? 15;
}

export function applyChatFontSize(size: ChatFontSize = getChatFontSize()): void {
  if (typeof document === "undefined") return;
  document.documentElement.style.setProperty("--chat-font-size", `${getChatFontSizePx(size)}px`);
}

export function setChatFontSize(size: ChatFontSize): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, size);
  applyChatFontSize(size);
  window.dispatchEvent(new CustomEvent(CHAT_FONT_SIZE_EVENT, { detail: size }));
}

export function subscribeChatFontSize(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handler = () => onChange();
  window.addEventListener(CHAT_FONT_SIZE_EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(CHAT_FONT_SIZE_EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}
