"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock3, GitBranch, HelpCircle, LoaderCircle, Search, ShieldCheck, Sparkles } from "lucide-react";

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
  qaMode,
  isActive = false
}: {
  route?: RouteEvent;
  plannerSteps: PlannerStep[];
  deepTrace: DeepTraceStep[];
  evidenceBundle?: EvidenceBundle;
  qaMode?: "quick" | "deep";
  isActive?: boolean;
}) {
  const [elapsedSec, setElapsedSec] = useState(0);
  const latestPlannerStep = plannerSteps[plannerSteps.length - 1];

  useEffect(() => {
    if (!isActive) {
      setElapsedSec(0);
      return;
    }

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSec(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isActive]);

  const hasRoute = !!route;
  const hasPlanner = plannerSteps.length > 0;
  const hasDeepTrace = deepTrace.length > 0;
  const hasEvidenceBundle = !!evidenceBundle;
  const hasAnswerStep = plannerSteps.some((step) => step.stage === "answer_synthesis");
  const isDeep = qaMode === "deep";

  const steps = useMemo(() => {
    type StepStatus = "pending" | "running" | "done";
    const doneWhenIdle = !isActive;
    const routeDone = hasRoute;
    const retrievalDone = hasEvidenceBundle || hasDeepTrace || plannerSteps.length >= 2;
    const coverageDone = hasEvidenceBundle;
    const answerDone = doneWhenIdle && (hasEvidenceBundle || hasAnswerStep);

    return [
      {
        icon: ShieldCheck,
        title: "边界检查",
        detail: "医疗安全与问答范围过滤",
        status: "done" as StepStatus
      },
      {
        icon: GitBranch,
        title: "路由选择",
        detail: `${compactRoute(route)}${route?.executed_routes?.length ? ` · ${route.executed_routes.join(" -> ")}` : ""}`,
        status: routeDone ? "done" as StepStatus : isActive ? "running" as StepStatus : "pending" as StepStatus
      },
      {
        icon: Search,
        title: "检索执行",
        detail: plannerSteps.length ? `${plannerSteps.length} 个规划步骤` : "图谱 / FFSR / 病例索引 / 补召回",
        status: retrievalDone ? "done" as StepStatus : (isActive && routeDone) ? "running" as StepStatus : "pending" as StepStatus
      },
      {
        icon: HelpCircle,
        title: isDeep ? "Deep 补证据" : "证据覆盖",
        detail: isDeep ? `${deepTrace.length} 个 deep trace 步骤` : evidenceSummary(evidenceBundle),
        status: coverageDone ? "done" as StepStatus : (isActive && (retrievalDone || hasPlanner)) ? "running" as StepStatus : "pending" as StepStatus
      },
      {
        icon: Sparkles,
        title: "证据约束生成",
        detail: evidenceSummary(evidenceBundle),
        status: answerDone ? "done" as StepStatus : (isActive && (hasEvidenceBundle || hasAnswerStep)) ? "running" as StepStatus : "pending" as StepStatus
      }
    ];
  }, [deepTrace.length, evidenceBundle, hasAnswerStep, hasEvidenceBundle, hasPlanner, hasRoute, hasDeepTrace, isActive, isDeep, plannerSteps.length, route]);

  if (!isActive && !route && !plannerSteps.length && !deepTrace.length && !evidenceBundle) {
    return null;
  }

  const runningIndex = steps.findIndex((step) => step.status === "running");
  const doneCount = steps.filter((step) => step.status === "done").length;
  const progress = Math.min(100, Math.max(12, Math.round(((doneCount + (runningIndex >= 0 ? 0.55 : 0)) / steps.length) * 100)));
  const currentStep = runningIndex >= 0 ? steps[runningIndex] : steps[Math.min(doneCount, steps.length - 1)];
  const liveDetail = latestPlannerStep
    ? `${latestPlannerStep.label}${latestPlannerStep.detail ? ` · ${latestPlannerStep.detail}` : ""}`
    : currentStep.detail;

  return (
    <div className="mb-4 rounded-3xl border border-[rgba(13,37,48,0.12)] bg-white/70 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-[var(--color-ink-soft)]">
            Retrieval Chain
          </div>
          <div className="text-sm font-semibold text-[var(--color-ink)]">完整检索与生成链路</div>
        </div>
        <div className="flex items-center gap-2">
          {isActive && (
            <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(15,139,141,0.12)] px-3 py-1 text-xs font-medium text-[var(--color-ocean)]">
              <LoaderCircle size={13} className="animate-spin" />
              处理中
            </span>
          )}
          <span className="rounded-full bg-[rgba(13,37,48,0.08)] px-3 py-1 text-xs text-[var(--color-ink-soft)]">
            {qaMode ?? "quick"}
          </span>
        </div>
      </div>
      {isActive && (
        <div className="mb-3 rounded-2xl border border-[rgba(15,139,141,0.18)] bg-[rgba(15,139,141,0.08)] p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="font-medium text-[var(--color-ink)]">
              当前：{currentStep.title}
              <span className="ml-2 font-normal text-[var(--color-ink-soft)]">{liveDetail}</span>
            </div>
            <span className="inline-flex items-center gap-1 text-[var(--color-ink-soft)]">
              <Clock3 size={13} />
              {elapsedSec ? `${elapsedSec}s` : "刚刚开始"}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/70">
            <div
              className="h-full rounded-full bg-[var(--color-ocean)] transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-2 grid gap-2 text-[11px] text-[var(--color-ink-soft)] sm:grid-cols-4">
            <span>路由：{hasRoute ? compactRoute(route) : "等待中"}</span>
            <span>规划：{plannerSteps.length} 步</span>
            <span>Deep：{deepTrace.length} 步</span>
            <span>证据：{hasEvidenceBundle ? evidenceSummary(evidenceBundle) : "生成中"}</span>
          </div>
        </div>
      )}
      <div className="grid gap-2 lg:grid-cols-5">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isDone = step.status === "done";
          const isRunning = step.status === "running";
          return (
            <div
              className={`rounded-2xl border p-3 ${
                isDone
                  ? "border-[rgba(47,111,115,0.28)] bg-[rgba(47,111,115,0.08)]"
                  : isRunning
                    ? "border-[rgba(15,139,141,0.34)] bg-[rgba(15,139,141,0.10)] shadow-[0_0_0_1px_rgba(15,139,141,0.08)]"
                  : "border-[var(--color-line)] bg-white/60"
              }`}
              key={step.title}
            >
              <div className="mb-2 flex items-center justify-between">
                <Icon size={16} className={isDone || isRunning ? "text-[var(--color-ember)]" : "text-[var(--color-ink-soft)]"} />
                {isDone && <CheckCircle2 size={14} className="text-[var(--color-ocean)]" />}
                {isRunning && <LoaderCircle size={14} className="animate-spin text-[var(--color-ocean)]" />}
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
