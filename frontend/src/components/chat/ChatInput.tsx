"use client";

import { Layers, SendHorizonal } from "lucide-react";
import { useState } from "react";

export function ChatInput({
  disabled,
  mode,
  onModeChange,
  fullEvidenceMode,
  onFullEvidenceModeChange,
  onSend
}: {
  disabled: boolean;
  mode: "quick" | "deep";
  onModeChange: (mode: "quick" | "deep") => void;
  fullEvidenceMode: boolean;
  onFullEvidenceModeChange: (enabled: boolean) => void;
  onSend: (value: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const submit = () => {
    const nextValue = value.trim();
    if (!nextValue) {
      return;
    }
    void onSend(nextValue);
    setValue("");
  };

  return (
    <div className="panel rounded-[28px] p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white/70 p-1">
            <button
              className={`rounded-full px-4 py-2 text-sm transition ${
                mode === "quick" ? "bg-ocean text-white" : "text-[var(--color-ink-soft)]"
              }`}
              onClick={() => onModeChange("quick")}
              type="button"
            >
              快速模式
            </button>
            <button
              className={`rounded-full px-4 py-2 text-sm transition ${
                mode === "deep" ? "bg-[var(--color-ember)] text-white" : "text-[var(--color-ink-soft)]"
              }`}
              onClick={() => onModeChange("deep")}
              type="button"
            >
              深度模式
            </button>
          </div>
          <button
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-2 text-sm transition ${
              fullEvidenceMode
                ? "border-[rgba(15,139,141,0.45)] bg-[rgba(15,139,141,0.14)] text-[var(--color-ocean)]"
                : "border-[var(--color-line)] bg-white/70 text-[var(--color-ink-soft)]"
            }`}
            onClick={() => onFullEvidenceModeChange(!fullEvidenceMode)}
            type="button"
            title="开启后会把所有检索到的完整证据发给 LLM，以回答质量为优先"
          >
            <Layers size={15} />
            {fullEvidenceMode ? "全证据模式" : "精简证据"}
          </button>
        </div>
        <p className="text-sm text-[var(--color-ink-soft)]">
          {mode === "quick" ? "固定工程链路，优先稳定与速度。" : "启用 Agent 与多源证据，优先完整性。"}
          {fullEvidenceMode && " 全证据模式：把所有证据完整送入 LLM。"}
        </p>
      </div>
      <textarea
        className="min-h-28 w-full resize-none rounded-[22px] border border-[var(--color-line)] bg-white/70 px-4 py-3 outline-none disabled:cursor-not-allowed disabled:bg-[rgba(13,37,48,0.04)]"
        disabled={disabled}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        }}
        placeholder="输入你的问题，Cmd/Ctrl + Enter 发送"
        value={value}
      />
      <div className="mt-3 flex items-center justify-between">
        <p className="text-sm text-[var(--color-ink-soft)]">
          当前走统一问答接口，返回答案、路由与证据。
        </p>
        <button
          className="flex items-center gap-2 rounded-full bg-ocean px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:bg-[rgba(15,139,141,0.45)]"
          disabled={disabled || !value.trim()}
          onClick={submit}
          type="button"
        >
          <SendHorizonal size={16} />
          发送
        </button>
      </div>
    </div>
  );
}
