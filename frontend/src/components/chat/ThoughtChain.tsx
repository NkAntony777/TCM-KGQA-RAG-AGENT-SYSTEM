"use client";

import { TerminalSquare } from "lucide-react";

import type { ToolCall } from "@/lib/api";

function summarizeInput(toolCall: ToolCall) {
  try {
    const parsed = JSON.parse(toolCall.input);
    if (toolCall.tool === "tcm_route_search") {
      return `query: ${parsed.query ?? "n/a"} / top_k: ${parsed.top_k ?? "n/a"}`;
    }
    if (toolCall.tool === "tcm_hybrid_search") {
      return `query: ${parsed.query ?? "n/a"} / top_k: ${parsed.top_k ?? "n/a"} / candidate_k: ${parsed.candidate_k ?? "n/a"}`;
    }
    if (toolCall.tool === "tcm_entity_lookup") {
      return `name: ${parsed.name ?? "n/a"} / top_k: ${parsed.top_k ?? "n/a"}`;
    }
    if (toolCall.tool === "tcm_path_query") {
      return `start: ${parsed.start ?? "n/a"} / end: ${parsed.end ?? "n/a"} / max_hops: ${parsed.max_hops ?? "n/a"}`;
    }
    if (toolCall.tool === "tcm_syndrome_chain") {
      return `symptom: ${parsed.symptom ?? "n/a"} / top_k: ${parsed.top_k ?? "n/a"}`;
    }
  } catch {
    return toolCall.input;
  }

  return toolCall.input;
}

export function ThoughtChain({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (!toolCalls.length) {
    return null;
  }

  return (
    <details className="mb-4 rounded-3xl border border-[rgba(212,106,74,0.18)] bg-[rgba(212,106,74,0.08)] p-4">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-[var(--color-ember)]">
        <TerminalSquare size={16} />
        工具调用 {toolCalls.length} 次
      </summary>
      <div className="mt-3 space-y-3">
        {toolCalls.map((toolCall, index) => (
          <div className="rounded-2xl bg-white/70 p-3" key={`${toolCall.tool}-${index}`}>
            <div className="mb-2 text-sm font-medium">
              {toolCall.tool}
            </div>
            {toolCall.meta && (
              <div className="mb-2 rounded-2xl bg-[rgba(13,37,48,0.06)] p-3 text-xs">
                <div className="mb-1 font-medium text-[var(--color-ink-soft)]">Meta</div>
                <div>backend: {toolCall.meta.backend ?? "n/a"}</div>
                <div>trace_id: {toolCall.meta.trace_id ?? "n/a"}</div>
                {toolCall.meta.status && <div>status: {toolCall.meta.status}</div>}
                {toolCall.meta.final_route && <div>final_route: {toolCall.meta.final_route}</div>}
                {toolCall.meta.warning && <div>warning: {toolCall.meta.warning}</div>}
              </div>
            )}
            <div className="space-y-2 text-xs">
              <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3">
                <div className="mb-1 font-medium text-[var(--color-ink-soft)]">Summary</div>
                <div className="mono whitespace-pre-wrap">{summarizeInput(toolCall)}</div>
                <div className="mt-2 text-[11px] text-[var(--color-ink-soft)]">
                  原始工具输出已隐藏，证据与路由信息请看上方卡片。
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
