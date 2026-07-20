export type LLMModelFamily = "doubao" | "deepseek" | "mock";

export interface LLMModelPreset {
  id: string;
  label: string;
  description?: string;
  family: LLMModelFamily;
  provider?: string;
  webSearch?: boolean;
}

/** 可选模型列表 — 切换时通过 PUT /system/llm-config 写入当前用户配置 */
export const LLM_MODEL_PRESETS: LLMModelPreset[] = [
  {
    id: "doubao-seed-2-1-pro-260628",
    label: "豆包 Seed 2.1 Pro",
    description: "更强推理能力",
    family: "doubao"
  },
  {
    id: "doubao-seed-2-1-turbo-260628",
    label: "豆包 Seed 2.1 Turbo",
    description: "默认 · 快速响应",
    family: "doubao"
  },
  {
    id: "doubao-seed-evolving",
    label: "豆包 Seed Evolving",
    description: "持续进化模型",
    family: "doubao"
  },
  {
    id: "deepseek-v4-pro-260425",
    label: "DeepSeek V4 Pro",
    description: "强推理",
    family: "deepseek",
    webSearch: true
  },
  {
    id: "deepseek-v4-flash-260425",
    label: "DeepSeek V4 Flash",
    description: "快速响应",
    family: "deepseek"
  },
  {
    id: "mock",
    label: "Mock 离线",
    description: "无 API Key 演示",
    family: "mock",
    provider: "mock"
  }
];

export function findModelPreset(modelId: string, provider?: string): LLMModelPreset | undefined {
  if (provider === "mock" || modelId === "mock") {
    return LLM_MODEL_PRESETS.find((p) => p.family === "mock");
  }
  return LLM_MODEL_PRESETS.find((p) => p.id === modelId);
}

export function resolveModelLabel(modelId: string, provider?: string): string {
  return findModelPreset(modelId, provider)?.label ?? modelId;
}

export function isModelUnlocked(
  preset: LLMModelPreset,
  unlockedFamilies: string[] | undefined
): boolean {
  if (preset.family === "mock") return true;
  return (unlockedFamilies ?? []).includes(preset.family);
}

export function buildModelOptions(
  currentModel: string,
  provider?: string,
  unlockedFamilies?: string[]
): LLMModelPreset[] {
  const options = LLM_MODEL_PRESETS.filter((p) => isModelUnlocked(p, unlockedFamilies));
  if (!findModelPreset(currentModel, provider) && currentModel) {
    options.unshift({
      id: currentModel,
      label: currentModel,
      description: "当前自定义模型",
      family: provider === "mock" ? "mock" : "doubao",
      provider
    });
  }
  return options;
}
