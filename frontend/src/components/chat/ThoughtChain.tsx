"use client";

import { Activity, TerminalSquare } from "lucide-react";

import type { DeepTraceStep, EvidenceBundle, PlannerStep, SkillMeta, ToolCall } from "@/lib/api";

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

function InfoSection({ title, items }: { title: string; items: string[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="rounded-2xl bg-white/70 p-3 text-xs">
      <div className="mb-2 font-medium text-[var(--color-ink-soft)]">{title}</div>
      <div className="space-y-1">
        {items.map((item, index) => (
          <div key={`${item}-${index}`}>{item}</div>
        ))}
      </div>
    </div>
  );
}

function SkillDetails({ step, skill }: { step: PlannerStep; skill?: SkillMeta }) {
  if (!step.skill || !skill) {
    return null;
  }

  const preferredTools = skill.preferred_tools ?? [];
  const workflowSteps = skill.workflow_steps ?? [];
  const stopRules = skill.stop_rules ?? [];

  return (
    <details className="mt-2 rounded-2xl bg-white/80 p-3">
      <summary className="cursor-pointer font-medium text-[var(--color-ink)]">
        Skill: {step.skill}
      </summary>
      <div className="mt-2 space-y-2 text-[11px] text-[var(--color-ink-soft)]">
        <div>{skill.description}</div>
        {!!preferredTools.length && <div>preferred_tools: {preferredTools.join(", ")}</div>}
        {!!workflowSteps.length && <div>workflow: {workflowSteps.slice(0, 2).join(" / ")}</div>}
        {!!stopRules.length && <div>stop: {stopRules[0]}</div>}
      </div>
    </details>
  );
}

function CoverageCard({ bundle }: { bundle?: EvidenceBundle }) {
  const coverage = bundle?.coverage;
  if (!bundle || !coverage) {
    return null;
  }

  const gaps = Array.isArray(coverage.gaps) ? coverage.gaps.map((item) => String(item)) : [];

  return (
    <div className="rounded-2xl bg-white/70 p-3 text-xs">
      <div className="mb-2 font-medium text-[var(--color-ink-soft)]">Coverage</div>
      <div className="grid gap-2 md:grid-cols-2">
        <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3">
          <div>factual_count: {coverage.factual_count ?? 0}</div>
          <div>case_count: {coverage.case_count ?? 0}</div>
          <div>evidence_path_count: {coverage.evidence_path_count ?? 0}</div>
          <div>sufficient: {coverage.sufficient ? "yes" : "no"}</div>
        </div>
        <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3">
          <div className="mb-1 font-medium text-[var(--color-ink-soft)]">Remaining Gaps</div>
          <div>{gaps.length ? gaps.join(" / ") : "none"}</div>
        </div>
      </div>
    </div>
  );
}

function DeepTraceCard({ steps }: { steps: DeepTraceStep[] }) {
  if (!steps.length) {
    return null;
  }

  return (
    <div className="rounded-2xl bg-white/70 p-3 text-xs">
      <div className="mb-2 flex items-center gap-2 font-medium text-[var(--color-ink-soft)]">
        <Activity size={14} />
        Deep Trace
      </div>
      <div className="space-y-2">
        {steps.map((step) => {
          const newEvidence = Array.isArray(step.new_evidence) ? step.new_evidence : [];
          const gaps = Array.isArray(step.coverage_after_step?.gaps)
            ? step.coverage_after_step?.gaps?.map((item) => String(item))
            : [];
          return (
            <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3" key={`deep-trace-${step.step}`}>
              <div className="font-medium text-[var(--color-ink)]">
                step {step.step} · {step.tool ?? "followup"}
              </div>
              <div className="mt-1 text-[var(--color-ink-soft)]">
                skill: {step.skill ?? "n/a"}
              </div>
              {step.why_this_step && (
                <div className="mt-1 text-[var(--color-ink-soft)]">
                  why: {step.why_this_step}
                </div>
              )}
              {step.input && Object.keys(step.input).length > 0 && (
                <div className="mono mt-2 whitespace-pre-wrap rounded-2xl bg-white/80 p-2 text-[11px]">
                  {JSON.stringify(step.input, null, 2)}
                </div>
              )}
              <div className="mt-2 text-[var(--color-ink-soft)]">
                new_evidence: {newEvidence.length}
              </div>
              <div className="text-[var(--color-ink-soft)]">
                remaining_gaps: {gaps.length ? gaps.join(" / ") : "none"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ThoughtChain({
  toolCalls,
  plannerSteps,
  deepTrace,
  evidenceBundle,
  notes,
  citations,
  qaMode,
  skills
}: {
  toolCalls: ToolCall[];
  plannerSteps: PlannerStep[];
  deepTrace: DeepTraceStep[];
  evidenceBundle?: EvidenceBundle;
  notes: string[];
  citations: string[];
  qaMode?: "quick" | "deep";
  skills: SkillMeta[];
}) {
  const safeToolCalls = toolCalls ?? [];
  const safePlannerSteps = plannerSteps ?? [];
  const safeDeepTrace = deepTrace ?? [];
  const safeNotes = notes ?? [];
  const safeCitations = citations ?? [];
  const safeSkills = skills ?? [];

  if (!safeToolCalls.length && !safePlannerSteps.length && !safeDeepTrace.length && !safeNotes.length && !safeCitations.length && !evidenceBundle) {
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

                return (
                  <div className="rounded-2xl bg-[rgba(13,37,48,0.06)] p-3" key={`${step.stage}-${index}`}>
                    <div className="font-medium text-[var(--color-ink)]">{step.label}</div>
                    <div className="mt-1 text-[var(--color-ink-soft)]">{step.detail || step.stage}</div>
                    <SkillDetails step={step} skill={skill} />
                  </div>
                );
              })}
            </div>
          </div>
        )}
        <DeepTraceCard steps={safeDeepTrace} />
        <CoverageCard bundle={evidenceBundle} />
        <InfoSection title="Notes" items={safeNotes} />
        <InfoSection title="Citations" items={safeCitations} />
        {safeToolCalls.map((toolCall, index) => (
          <div className="rounded-2xl bg-white/70 p-3" key={`${toolCall.tool}-${index}`}>
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
        ))}
      </div>
    </details>
  );
}
