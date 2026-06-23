"use client";

import { Send } from "lucide-react";

interface CarpetInquiryPanelProps {
  reason: string;
  questions: string[];
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export function CarpetInquiryPanel({
  reason,
  questions,
  value,
  onChange,
  onSubmit,
  disabled,
}: CarpetInquiryPanelProps) {
  return (
    <div className="carpet-inquiry-panel" role="dialog" aria-label="询问员问询">
      <div className="carpet-inquiry-panel-inner">
        <p className="carpet-inquiry-title">💬 询问员</p>
        <p className="carpet-inquiry-reason">{reason}</p>
        <ul className="carpet-inquiry-questions">
          {questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
        <textarea
          className="carpet-inquiry-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="在此回复…"
          disabled={disabled}
          rows={3}
        />
        <button
          type="button"
          className="studio-launch-btn studio-launch-btn-sm carpet-inquiry-submit"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
        >
          <Send size={14} /> 提交补充信息
        </button>
      </div>
    </div>
  );
}
