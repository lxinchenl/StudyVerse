"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Settings2, Type, Zap } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { fetchLLMConfig, saveLLMConfig, testLLMConfig, type LLMConfig } from "@/lib/api";
import {
  CHAT_FONT_SIZE_OPTIONS,
  getChatFontSize,
  setChatFontSize,
  type ChatFontSize
} from "@/lib/uiPreferences";

const DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3";
const DEFAULT_MODEL = "doubao-seed-2-0-lite-260428";

export default function SettingsPage() {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [provider, setProvider] = useState("openai_compatible");
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState("");
  const [chatFontSize, setChatFontSizeState] = useState<ChatFontSize>("md");

  useEffect(() => {
    setChatFontSizeState(getChatFontSize());
  }, []);

  useEffect(() => {
    fetchLLMConfig()
      .then((data) => {
        setConfig(data);
        setProvider(data.provider);
        setBaseUrl(data.baseUrl);
        setModel(data.model);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload: {
        provider: string;
        base_url: string;
        model: string;
        api_key?: string;
      } = {
        provider,
        base_url: baseUrl.trim(),
        model: model.trim()
      };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      const saved = await saveLLMConfig(payload);
      setConfig(saved);
      setApiKey("");
      setMessage("配置已保存，后续对话将使用新模型。");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setError("");
    setTestResult("");
    try {
      const result = await testLLMConfig();
      if (result.ok) {
        setTestResult(result.preview);
      } else {
        setError(result.error || "模型调用失败");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "测试失败");
    } finally {
      setTesting(false);
    }
  }

  return (
    <AppShell title="设置" subtitle="模型接入与聊天页显示偏好">
      {loading ? <p className="muted">加载配置中...</p> : null}
      {error ? <p className="muted" style={{ color: "var(--danger)" }}>{error}</p> : null}
      {message ? <p className="muted" style={{ color: "var(--success)" }}>{message}</p> : null}

      <section className="card" style={{ maxWidth: 720 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <Settings2 size={20} />
          <h3 style={{ margin: 0 }}>LLM 接入</h3>
        </div>

        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <label>
            <span className="muted">Provider</span>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              style={{ width: "100%", marginTop: 6, padding: "10px 12px" }}
            >
              <option value="openai_compatible">豆包 / OpenAI 兼容</option>
              <option value="mock">Mock（离线演示）</option>
            </select>
          </label>

          <label>
            <span className="muted">Base URL</span>
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={DEFAULT_BASE_URL}
              style={{ width: "100%", marginTop: 6, padding: "10px 12px" }}
            />
          </label>

          <label>
            <span className="muted">Model</span>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={DEFAULT_MODEL}
              style={{ width: "100%", marginTop: 6, padding: "10px 12px" }}
            />
          </label>

          <label>
            <span className="muted">API Key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={config?.apiKeySet ? `已配置 ${config.apiKeyHint}，留空则不修改` : "输入 ARK_API_KEY"}
              style={{ width: "100%", marginTop: 6, padding: "10px 12px" }}
            />
          </label>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? <Loader2 size={16} /> : <CheckCircle2 size={16} />}
              {saving ? "保存中..." : "保存配置"}
            </button>
            <button type="button" className="btn-secondary" onClick={handleTest} disabled={testing || provider === "mock"}>
              {testing ? <Loader2 size={16} /> : <Zap size={16} />}
              {testing ? "测试中..." : "测试连接"}
            </button>
          </div>
        </form>

        {config ? (
          <p className="muted" style={{ marginTop: 16 }}>
            当前状态：{config.ready ? "已就绪" : "未配置 API Key"} · Provider: {config.provider}
          </p>
        ) : null}

        {testResult ? (
          <div className="card" style={{ marginTop: 16, background: "var(--primary-soft)" }}>
            <strong>测试回复</strong>
            <p style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{testResult}</p>
          </div>
        ) : null}
      </section>

      <section className="card" style={{ maxWidth: 720, marginTop: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <Type size={20} />
          <h3 style={{ margin: 0 }}>聊天页字体</h3>
        </div>
        <p className="muted" style={{ marginTop: 0 }}>
          调整「多 Agent 学习」对话区的文字大小，设置会保存在本浏览器。
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {CHAT_FONT_SIZE_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={chatFontSize === option.value ? "btn-primary" : "btn-secondary"}
              onClick={() => {
                setChatFontSizeState(option.value);
                setChatFontSize(option.value);
              }}
            >
              {option.label}（{option.px}px）
            </button>
          ))}
        </div>
      </section>

      <section className="card" style={{ maxWidth: 720, marginTop: 20 }}>
        <h3>豆包示例</h3>
        <p className="muted">默认 Base URL：<code>{DEFAULT_BASE_URL}</code></p>
        <p className="muted">也可在项目根目录 <code>.env</code> 中设置 <code>ARK_API_KEY=...</code>，首次启动会自动读取。</p>
      </section>
    </AppShell>
  );
}
