"use client";

import { ArrowRight, Bot, Check, ChevronDown, Loader2, Paperclip, Sparkles } from "lucide-react";
import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { fetchLLMConfig, saveLLMConfig } from "@/lib/api";
import {
  buildModelOptions,
  findModelPreset,
  LLM_MODEL_PRESETS,
  resolveModelLabel,
  type LLMModelPreset
} from "@/lib/llm-models";

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({ minHeight, maxHeight }: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      if (reset) {
        textarea.style.height = `${minHeight}px`;
        return;
      }

      textarea.style.height = `${minHeight}px`;
      const newHeight = Math.max(
        minHeight,
        Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY)
      );
      textarea.style.height = `${newHeight}px`;
    },
    [minHeight, maxHeight]
  );

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) textarea.style.height = `${minHeight}px`;
  }, [minHeight]);

  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

function DoubaoIcon({ className }: { className?: string }) {
  return (
    <svg className={cn("h-4 w-4", className)} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" fill="url(#doubao-grad)" />
      <defs>
        <linearGradient id="doubao-grad" x1="4" y1="4" x2="20" y2="20">
          <stop stopColor="#3b82f6" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <path
        d="M8 9.5h8M8 12.5h5.5"
        stroke="#fff"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ModelIcon({ preset }: { preset: LLMModelPreset }) {
  if (preset.provider === "mock") {
    return <Bot className="h-4 w-4 text-muted-foreground" />;
  }
  return <DoubaoIcon />;
}

export interface ChatPromptInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  onModelChange?: (modelId: string, provider?: string) => void;
  onFileSelect?: (files: FileList) => void | Promise<void>;
  fileUploading?: boolean;
}

export function ChatPromptInput({
  value,
  onChange,
  onSubmit,
  loading = false,
  disabled = false,
  placeholder = "输入你的问题，Shift+Enter 换行…",
  onModelChange,
  onFileSelect,
  fileUploading = false
}: ChatPromptInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight: 72,
    maxHeight: 300
  });

  const [modelOptions, setModelOptions] = useState<LLMModelPreset[]>(LLM_MODEL_PRESETS);
  const [selectedModelId, setSelectedModelId] = useState("doubao-seed-2-0-lite-260428");
  const [selectedProvider, setSelectedProvider] = useState<string | undefined>();
  const [modelLoading, setModelLoading] = useState(true);
  const [modelSwitching, setModelSwitching] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);

  const selectedLabel = resolveModelLabel(selectedModelId, selectedProvider);
  const selectedPreset =
    findModelPreset(selectedModelId, selectedProvider) ??
    ({ id: selectedModelId, label: selectedLabel } satisfies LLMModelPreset);
  const inputDisabled = disabled || loading || modelSwitching || fileUploading;

  useEffect(() => {
    let cancelled = false;
    fetchLLMConfig()
      .then((cfg) => {
        if (cancelled) return;
        setSelectedModelId(cfg.model);
        setSelectedProvider(cfg.provider);
        setModelOptions(buildModelOptions(cfg.model, cfg.provider));
      })
      .catch(() => {
        if (!cancelled) setModelError("无法加载模型配置");
      })
      .finally(() => {
        if (!cancelled) setModelLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleModelSelect(preset: LLMModelPreset) {
    if (preset.id === selectedModelId && preset.provider === selectedProvider) return;
    setModelSwitching(true);
    setModelError(null);
    try {
      const payload: { model: string; provider?: string } = { model: preset.id };
      if (preset.provider) payload.provider = preset.provider;
      else if (selectedProvider === "mock") payload.provider = "openai_compatible";

      const saved = await saveLLMConfig(payload);
      setSelectedModelId(saved.model);
      setSelectedProvider(saved.provider);
      setModelOptions(buildModelOptions(saved.model, saved.provider));
      onModelChange?.(saved.model, saved.provider);
    } catch (err) {
      setModelError(err instanceof Error ? err.message : "切换模型失败");
    } finally {
      setModelSwitching(false);
    }
  }

  function submit() {
    if (!value.trim() || inputDisabled) return;
    onSubmit();
    adjustHeight(true);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="chat-prompt-shell">
      {modelError ? <p className="chat-prompt-model-error">{modelError}</p> : null}
      <div className="chat-prompt-card">
        <div className="relative flex flex-col">
          <div className="overflow-y-auto" style={{ maxHeight: "400px" }}>
            <Textarea
              id="learn-chat-input"
              value={value}
              placeholder={placeholder}
              disabled={inputDisabled}
              className={cn(
                "chat-prompt-textarea w-full rounded-xl rounded-b-none border-none bg-transparent px-4 py-3 shadow-none resize-none",
                "placeholder:text-muted-foreground/80 focus-visible:ring-0 focus-visible:ring-offset-0",
                "min-h-[72px]"
              )}
              ref={textareaRef}
              onKeyDown={handleKeyDown}
              onChange={(e) => {
                onChange(e.target.value);
                adjustHeight();
              }}
            />
          </div>

          <div className="chat-prompt-toolbar h-14 rounded-b-xl flex items-center">
            <div className="absolute left-3 right-3 bottom-3 flex items-center justify-between w-[calc(100%-24px)]">
              <div className="flex items-center gap-2 min-w-0">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={modelLoading || modelSwitching}
                      className="flex items-center gap-1.5 h-8 max-w-[200px] pl-1.5 pr-2 text-xs rounded-lg hover:bg-primary-soft"
                    >
                      {modelSwitching ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
                      ) : (
                        <AnimatePresence mode="wait">
                          <motion.div
                            key={selectedModelId}
                            initial={{ opacity: 0, y: -4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 4 }}
                            transition={{ duration: 0.15 }}
                            className="flex items-center gap-1.5 min-w-0"
                          >
                            <ModelIcon preset={selectedPreset} />
                            <span className="truncate">{selectedLabel}</span>
                            <ChevronDown className="h-3 w-3 opacity-50 shrink-0" />
                          </motion.div>
                        </AnimatePresence>
                      )}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="min-w-[14rem]">
                    {modelOptions.map((preset) => {
                      const active =
                        preset.provider === "mock"
                          ? selectedProvider === "mock"
                          : selectedModelId === preset.id && selectedProvider !== "mock";
                      return (
                        <DropdownMenuItem
                          key={`${preset.id}-${preset.provider ?? "default"}`}
                          onSelect={() => void handleModelSelect(preset)}
                          className="flex items-center justify-between gap-3 py-2"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <ModelIcon preset={preset} />
                            <div className="min-w-0">
                              <div className="truncate">{preset.label}</div>
                              {preset.description ? (
                                <div className="text-[11px] text-muted-foreground truncate">
                                  {preset.description}
                                </div>
                              ) : null}
                            </div>
                          </div>
                          {active ? <Check className="h-4 w-4 text-primary shrink-0" /> : null}
                        </DropdownMenuItem>
                      );
                    })}
                  </DropdownMenuContent>
                </DropdownMenu>
                <div className="h-4 w-px bg-border mx-0.5 shrink-0" />
                <label
                  className={cn(
                    "chat-prompt-attach rounded-lg p-2 cursor-pointer shrink-0",
                    "bg-secondary hover:bg-accent text-muted-foreground hover:text-foreground",
                    "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1",
                    (inputDisabled || !onFileSelect) && "pointer-events-none opacity-50"
                  )}
                  aria-label="上传文件"
                  title="上传文件到个人目录"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    multiple
                    disabled={inputDisabled || !onFileSelect}
                    onChange={(e) => {
                      const files = e.target.files;
                      if (files?.length && onFileSelect) void onFileSelect(files);
                      e.target.value = "";
                    }}
                  />
                  {fileUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Paperclip className="h-4 w-4" />
                  )}
                </label>
                <div className="hidden sm:flex items-center gap-1 text-[11px] text-muted-foreground">
                  <Sparkles className="h-3 w-3" />
                  <span>多 Agent 协同</span>
                </div>
              </div>

              <button
                type="button"
                className={cn(
                  "chat-prompt-send rounded-lg p-2.5 transition-all",
                  value.trim() && !inputDisabled
                    ? "bg-primary text-primary-foreground shadow-sm hover:bg-primary-hover"
                    : "bg-secondary text-muted-foreground"
                )}
                aria-label="发送消息"
                disabled={!value.trim() || inputDisabled}
                onClick={submit}
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className={cn("h-4 w-4", value.trim() ? "opacity-100" : "opacity-40")} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export { ChatPromptInput as AI_Prompt };
