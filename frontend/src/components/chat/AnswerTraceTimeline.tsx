"use client";

import { CheckCircle2, GitBranch, HelpCircle, Search, ShieldCheck, Sparkles } from "lucide-react";

import type { DeepTraceStep, EvidenceBundle, PlannerStep, RouteEvent } from "@/lib/api";

function compactRoute(route?: RouteEvent) {
  if (!route) {
    return "等待路由";
  }
  return route.final_route || route.route || "unknown";
}

function evidenceSummary(bundle?: EvidenceBundle) {
  const coverage = bundle?.coverage;
  if (!coverage) {
    return "证据包生成中";
  }
  const factual = coverage.factual_count ?? 0;
  const paths = coverage.evidence_path_count ?? 0;
  const gaps = Array.isArray(coverage.gaps) ? coverage.gaps.length : 0;
  return `${factual} 条事实 / ${paths} 条路径 / ${gaps} 个缺口`;
}

export function AnswerTraceTimeline({
  route,
  plannerSteps,
  deepTrace,
  evidenceBundle,
  qaMode
}: {
  route?: RouteEvent;
  plannerSteps: PlannerStep[];
  deepTrace: DeepTraceStep[];
  evidenceBundle?: EvidenceBundle;
  qaMode?: "quick" | "deep";
}) {
  const steps = [
    {
      icon: ShieldCheck,
      title: "边界检查",
      detail: "医疗安全与问答范围过滤",
      active: true
    },
    {
      icon: GitBranch,
      title: "路由选择",
      detail: `${compactRoute(route)}${route?.executed_routes?.length ? ` · ${route.executed_routes.join(" -> ")}` : ""}`,
      active: !!route
    },
    {
      icon: Search,
      title: "检索执行",
      detail: plannerSteps.length ? `${plannerSteps.length} 个规划步骤` : "图谱 / FFSR / 病例索引 / 补召回",
      active: !!plannerSteps.length || !!route
    },
    {
      icon: HelpCircle,
      title: qaMode === "deep" ? "Deep 补证据" : "证据覆盖",
      detail: qaMode === "deep" ? `${deepTrace.length} 个 deep trace 步骤` : evidenceSummary(evidenceBundle),
      active: qaMode === "deep" ? !!deepTrace.length : !!evidenceBundle
    },
    {
      icon: Sparkles,
      title: "证据约束生成",
      detail: evidenceSummary(evidenceBundle),
      active: !!evidenceBundle
    }
  ];

  if (!route && !plannerSteps.length && !deepTrace.length && !evidenceBundle) {
    return null;
  }

  return (
    <div className="mb-4 rounded-3xl border border-[rgba(13,37,48,0.12)] bg-white/70 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-[var(--color-ink-soft)]">
            Retrieval Chain
          </div>
          <div className="text-sm font-semibold text-[var(--color-ink)]">完整检索与生成链路</div>
        </div>
        <span className="rounded-full bg-[rgba(13,37,48,0.08)] px-3 py-1 text-xs text-[var(--color-ink-soft)]">
          {qaMode ?? "quick"}
        </span>
      </div>
      <div className="grid gap-2 lg:grid-cols-5">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <div
              className={`rounded-2xl border p-3 ${
                step.active
                  ? "border-[rgba(47,111,115,0.28)] bg-[rgba(47,111,115,0.08)]"
                  : "border-[var(--color-line)] bg-white/60"
              }`}
              key={step.title}
            >
              <div className="mb-2 flex items-center justify-between">
                <Icon size={16} className={step.active ? "text-[var(--color-ember)]" : "text-[var(--color-ink-soft)]"} />
                {step.active && <CheckCircle2 size={14} className="text-[var(--color-leaf)]" />}
              </div>
              <div className="text-xs font-semibold text-[var(--color-ink)]">
                {index + 1}. {step.title}
              </div>
              <div className="mt-1 text-[11px] leading-5 text-[var(--color-ink-soft)]">
                {step.detail}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
