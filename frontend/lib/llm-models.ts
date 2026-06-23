export interface LLMModelPreset {
  id: string;
  label: string;
  description?: string;
  provider?: string;
}

/** 可选模型列表 — 切换时通过 PUT /system/llm-config 写入后端 */
export const LLM_MODEL_PRESETS: LLMModelPreset[] = [
  {
    id: "doubao-seed-2-0-lite-260428",
    label: "豆包 Seed 2.0 Lite",
    description: "默认 · 快速响应"
  },
  {
    id: "doubao-seed-2-0-pro-260428",
    label: "豆包 Seed 2.0 Pro",
    description: "更强推理能力"
  },
  {
    id: "doubao-seed-1-6-250615",
    label: "豆包 Seed 1.6",
    description: "均衡性价比"
  },
  {
    id: "mock",
    label: "Mock 离线",
    description: "无 API Key 演示",
    provider: "mock"
  }
];

export function findModelPreset(modelId: string, provider?: string): LLMModelPreset | undefined {
  if (provider === "mock") {
    return LLM_MODEL_PRESETS.find((p) => p.provider === "mock");
  }
  return LLM_MODEL_PRESETS.find((p) => p.id === modelId);
}

export function resolveModelLabel(modelId: string, provider?: string): string {
  return findModelPreset(modelId, provider)?.label ?? modelId;
}

export function buildModelOptions(currentModel: string, provider?: string): LLMModelPreset[] {
  const options = [...LLM_MODEL_PRESETS];
  if (!findModelPreset(currentModel, provider)) {
    options.unshift({
      id: currentModel,
      label: currentModel,
      description: "当前自定义模型",
      provider
    });
  }
  return options;
}
