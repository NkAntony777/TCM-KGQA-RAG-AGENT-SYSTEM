"use client";

import { GitBranch } from "lucide-react";

import type { RouteEvent } from "@/lib/api";

export function RouteCard({ route }: { route?: RouteEvent }) {
  if (!route) {
    return null;
  }

  const degradation = route.degradation ?? [];
  const traceIds = route.service_trace_ids ?? {};
  const backends = route.service_backends ?? {};

  return (
    <details className="mb-4 rounded-3xl border border-[rgba(34,96,145,0.18)] bg-[rgba(34,96,145,0.08)] p-4" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-[var(--color-ink)]">
        <GitBranch size={16} />
        路由 {route.route} / 实际执行 {route.final_route ?? route.route}
      </summary>
      <div className="mt-3 space-y-3 text-sm text-[var(--color-ink)]">
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-white/70 px-3 py-1">状态: {route.status}</span>
          {(route.executed_routes ?? []).length > 0 && (
            <span className="rounded-full bg-white/70 px-3 py-1">
              执行链路: {(route.executed_routes ?? []).join(" -> ")}
            </span>
          )}
        </div>
        <p className="leading-6 text-[var(--color-ink-soft)]">{route.reason}</p>
        {!!degradation.length && (
          <div className="rounded-2xl bg-white/70 p-3 text-xs">
            <div className="mb-1 font-medium text-[var(--color-ink-soft)]">降级记录</div>
            {degradation.map((item, index) => (
            <div key={`${item.from}-${item.to}-${index}`}>
                {item.from} {"->"} {item.to}: {item.reason}
              </div>
            ))}
          </div>
        )}
        {!!Object.keys(traceIds).length && (
          <div className="rounded-2xl bg-white/70 p-3 text-xs">
            <div className="mb-1 font-medium text-[var(--color-ink-soft)]">Trace / Backend</div>
            {Object.entries(traceIds).map(([service, traceId]) => (
              <div key={service} className="mb-1 last:mb-0">
                <span className="font-medium">{service}</span>: {traceId || "n/a"}
                {backends[service] ? ` (${backends[service]})` : ""}
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
