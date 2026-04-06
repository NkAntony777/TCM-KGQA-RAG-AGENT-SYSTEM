"use client";

import { TerminalSquare } from "lucide-react";

import type { PlannerStep, SkillMeta, ToolCall } from "@/lib/api";

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

export function ThoughtChain({
  toolCalls,
  plannerSteps,
  notes,
  citations,
  qaMode,
  skills
}: {
  toolCalls: ToolCall[];
  plannerSteps: PlannerStep[];
  notes: string[];
  citations: string[];
  qaMode?: "quick" | "deep";
  skills: SkillMeta[];
}) {
  const safeToolCalls = toolCalls ?? [];
  const safePlannerSteps = plannerSteps ?? [];
  const safeNotes = notes ?? [];
  const safeCitations = citations ?? [];
  const safeSkills = skills ?? [];

  if (!safeToolCalls.length && !safePlannerSteps.length && !safeNotes.length && !safeCitations.length) {
    return null;
  }

  const skillMap = new Map(safeSkills.map((skill) => [skill.name, skill]));

  return (
    <details className="mb-4 rounded-3xl border border-[rgba(212,106,74,0.18)] bg-[rgba(212,106,74,0.08)] p-4">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-[var(--color-ember)]">
        <TerminalSquare size={16} />
        {qaMode === "deep" ? "深度模式轨迹" : "问答轨迹"}
      </summary>
      <div className="mt-3 space-y-3">
        {!!safePlannerSteps.length && (
          <div className="rounded-2xl bg-white/70 p-3 text-xs">
            <div className="mb-2 font-medium text-[var(--color-ink-soft)]">Planner</div>
            <div className="space-y-2">
              {safePlannerSteps.map((step, index) => {
                const skill = step.skill ? skillMap.get(step.skill) : undefined;
                const preferredTools = skill?.preferred_tools ?? [];
                const workflowSteps = skill?.workflow_steps ?? [];
                const stopRules = skill?.stop_rules ?? [];

                return (
                  <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3" key={`${step.stage}-${index}`}>
                    <div className="font-medium text-[var(--color-ink)]">{step.label}</div>
                    <div className="mt-1 text-[var(--color-ink-soft)]">{step.detail || step.stage}</div>
                    {step.skill && skill && (
                      <details className="mt-2 rounded-2xl bg-white/80 p-3">
                        <summary className="cursor-pointer font-medium text-[var(--color-ink)]">
                          Skill: {step.skill}
                        </summary>
                        <div className="mt-2 space-y-2 text-[11px] text-[var(--color-ink-soft)]">
                          <div>{skill.description}</div>
                          {!!preferredTools.length && (
                            <div>preferred_tools: {preferredTools.join(", ")}</div>
                          )}
                          {!!workflowSteps.length && (
                            <div>
                              workflow: {workflowSteps.slice(0, 2).join(" / ")}
                            </div>
                          )}
                          {!!stopRules.length && (
                            <div>stop: {stopRules[0]}</div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {!!safeNotes.length && (
          <div className="rounded-2xl bg-white/70 p-3 text-xs">
            <div className="mb-2 font-medium text-[var(--color-ink-soft)]">Notes</div>
            <div className="space-y-1">
              {safeNotes.map((note, index) => (
                <div key={`${note}-${index}`}>{note}</div>
              ))}
            </div>
          </div>
        )}
        {!!safeCitations.length && (
          <div className="rounded-2xl bg-white/70 p-3 text-xs">
            <div className="mb-2 font-medium text-[var(--color-ink-soft)]">Citations</div>
            <div className="space-y-1">
              {safeCitations.map((citation, index) => (
                <div key={`${citation}-${index}`}>{citation}</div>
              ))}
            </div>
          </div>
        )}
        {safeToolCalls.map((toolCall, index) => (
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
        ))}
      </div>
    </details>
  );
}
