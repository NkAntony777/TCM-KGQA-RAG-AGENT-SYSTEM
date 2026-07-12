import type { ToolCall } from "@/lib/api";

const TOOL_SUMMARIES: Record<
  string,
  Array<{ key: string; label: string }>
> = {
  tcm_route_search: [
    { key: "query", label: "query" },
    { key: "top_k", label: "top_k" }
  ],
  tcm_hybrid_search: [
    { key: "query", label: "query" },
    { key: "top_k", label: "top_k" },
    { key: "candidate_k", label: "candidate_k" }
  ],
  tcm_entity_lookup: [
    { key: "name", label: "name" },
    { key: "top_k", label: "top_k" }
  ],
  tcm_path_query: [
    { key: "start", label: "start" },
    { key: "end", label: "end" },
    { key: "max_hops", label: "max_hops" }
  ],
  tcm_syndrome_chain: [
    { key: "symptom", label: "symptom" },
    { key: "top_k", label: "top_k" }
  ]
};

function summarizeInput(toolCall: ToolCall) {
  try {
    const parsed = JSON.parse(toolCall.input);
    const fields = TOOL_SUMMARIES[toolCall.tool];
    if (fields) {
      return fields.map(({ key, label }) => `${label}: ${parsed[key] ?? "n/a"}`).join(" / ");
    }
  } catch {
    return toolCall.input;
  }

  return toolCall.input;
}

export function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  return (
    <div className="rounded-2xl bg-white/70 p-3">
      <div className="mb-2 text-sm font-medium">{toolCall.tool}</div>
      {toolCall.meta && (
        <div className="mb-2 rounded-2xl bg-[rgba(13,37,48,0.06)] p-3 text-xs">
          <div className="mb-1 font-medium text-[var(--color-ink-soft)]">Meta</div>
          <div>backend: {toolCall.meta.backend ?? "n/a"}</div>
          <div>trace_id: {toolCall.meta.trace_id ?? "n/a"}</div>
          {toolCall.meta.status && <div>status: {toolCall.meta.status}</div>}
          {toolCall.meta.final_route && <div>final_route: {toolCall.meta.final_route}</div>}
          {toolCall.meta.reason && <div>reason: {toolCall.meta.reason}</div>}
          {toolCall.meta.path && <div>path: {toolCall.meta.path}</div>}
          {toolCall.meta.query && <div>query: {toolCall.meta.query}</div>}
          {typeof toolCall.meta.count === "number" && <div>count: {toolCall.meta.count}</div>}
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
  );
}
