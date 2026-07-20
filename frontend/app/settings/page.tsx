"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, Type, Zap } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth";
import { fetchLLMConfig, saveLLMConfig, testLLMConfig, type LLMConfig } from "@/lib/api";
import {
  CHAT_FONT_SIZE_OPTIONS,
  getChatFontSize,
  setChatFontSize,
  type ChatFontSize
} from "@/lib/uiPreferences";

export default function SettingsPage() {
  const { user } = useAuth();
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [doubaoKey, setDoubaoKey] = useState("");
  const [deepseekKey, setDeepseekKey] = useState("");
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
    if (!user) return;
    setLoading(true);
    fetchLLMConfig(user.id)
      .then(setConfig)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [user]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload: {
        doubao_api_key?: string;
        deepseek_api_key?: string;
      } = {};
      if (doubaoKey.trim()) payload.doubao_api_key = doubaoKey.trim();
      if (deepseekKey.trim()) payload.deepseek_api_key = deepseekKey.trim();
      if (!payload.doubao_api_key && !payload.deepseek_api_key) {
        setMessage("未填写新的 Key（已保留现有配置）");
        return;
      }
      const saved = await saveLLMConfig(user.id, payload);
      setConfig(saved);
      setDoubaoKey("");
      setDeepseekKey("");
      setMessage("API Key 已保存。聊天页将解锁对应厂商的模型。");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!user) return;
    setTesting(true);
    setError("");
    setTestResult("");
    try {
      const result = await testLLMConfig(user.id);
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
      {error ? (
        <p className="muted" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="muted" style={{ color: "var(--success)" }}>
          {message}
        </p>
      ) : null}

      <section className="card" style={{ maxWidth: 720 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <KeyRound size={20} />
          <h3 style={{ margin: 0 }}>LLM 接入</h3>
        </div>
        <p className="muted" style={{ marginTop: 0, marginBottom: 16 }}>
          模型与接口地址已内置。这里只需填写你自己的 API Key；填入后，聊天页即可切换对应厂商的模型。
          Key 与当前账号绑定，仅你本人可用。
        </p>

        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <label>
            <span className="muted">豆包 API Key</span>
            <input
              type="password"
              value={doubaoKey}
              onChange={(e) => setDoubaoKey(e.target.value)}
              placeholder={
                config?.doubaoApiKeySet
                  ? `已配置 ${config.doubaoApiKeyHint}，留空则不修改`
                  : "填写火山引擎 ARK API Key"
              }
              style={{ width: "100%", marginTop: 6, padding: "10px 12px" }}
              autoComplete="off"
            />
            <span className="muted" style={{ display: "block", marginTop: 4, fontSize: 12 }}>
              解锁：豆包 Seed 2.1 Pro / Turbo / Evolving
            </span>
          </label>

          <label>
            <span className="muted">DeepSeek API Key</span>
            <input
              type="password"
              value={deepseekKey}
              onChange={(e) => setDeepseekKey(e.target.value)}
              placeholder={
                config?.deepseekApiKeySet
                  ? `已配置 ${config.deepseekApiKeyHint}，留空则不修改`
                  : "填写 DeepSeek API Key"
              }
              style={{ width: "100%", marginTop: 6, padding: "10px 12px" }}
              autoComplete="off"
            />
            <span className="muted" style={{ display: "block", marginTop: 4, fontSize: 12 }}>
              解锁：DeepSeek V4 Pro / Flash
            </span>
          </label>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button type="submit" className="btn-primary" disabled={saving || !user}>
              {saving ? <Loader2 size={16} /> : <CheckCircle2 size={16} />}
              {saving ? "保存中..." : "保存 Key"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleTest}
              disabled={testing || !config?.ready || !user}
            >
              {testing ? <Loader2 size={16} /> : <Zap size={16} />}
              {testing ? "测试中..." : "测试当前模型"}
            </button>
          </div>
        </form>

        {config ? (
          <div className="muted" style={{ marginTop: 16, fontSize: 13, lineHeight: 1.6 }}>
            <div>
              豆包：{config.doubaoApiKeySet ? `已配置（${config.doubaoApiKeyHint}）` : "未配置"}
            </div>
            <div>
              DeepSeek：{config.deepseekApiKeySet ? `已配置（${config.deepseekApiKeyHint}）` : "未配置"}
            </div>
            <div>
              当前选用：{config.provider === "mock" ? "Mock 离线" : config.model}
            </div>
          </div>
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
    </AppShell>
  );
}
