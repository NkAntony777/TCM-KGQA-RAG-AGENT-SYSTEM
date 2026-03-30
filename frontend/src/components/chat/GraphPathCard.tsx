"use client";

import { Share2 } from "lucide-react";

import type { EvidenceItem } from "@/lib/api";

function formatSource(item: { source_book?: string; source_chapter?: string }) {
  const book = item.source_book?.trim();
  const chapter = item.source_chapter?.trim();
  if (book && chapter) {
    return `《${book}》 ${chapter}`;
  }
  if (book) {
    return `《${book}》`;
  }
  return chapter || "未知来源";
}

function formatEdge(edge: string) {
  return edge.replace("(逆向)", " ←").replace("(閫嗗悜)", " ←");
}

export function GraphPathCard({ items }: { items: EvidenceItem[] }) {
  const pathItems = items.filter((item) => item.source_type === "graph_path" && item.path_nodes?.length);
  if (!pathItems.length) {
    return null;
  }

  return (
    <details className="mb-4 rounded-3xl border border-[rgba(129,91,172,0.18)] bg-[rgba(129,91,172,0.08)] p-4" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-[var(--color-ink)]">
        <Share2 size={16} />
        图路径证据 {pathItems.length} 条
      </summary>
      <div className="mt-3 space-y-3">
        {pathItems.map((item, index) => (
          <div className="rounded-2xl bg-white/70 p-3" key={`${item.source}-${index}`}>
            <div className="mb-2 flex items-center justify-between gap-3 text-xs text-[var(--color-ink-soft)]">
              <span>{item.source}</span>
              <span>{item.score == null ? "n/a" : item.score.toFixed(3)}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-[var(--color-ink)]">
              {item.path_nodes?.map((node, nodeIndex) => (
                <div className="contents" key={`${node}-${nodeIndex}`}>
                  <span className="rounded-full bg-[rgba(129,91,172,0.12)] px-3 py-1">{node}</span>
                  {nodeIndex < (item.path_nodes?.length ?? 0) - 1 && (
                    <span className="text-[var(--color-ink-soft)]">{formatEdge(item.path_edges?.[nodeIndex] ?? "关联")}</span>
                  )}
                </div>
              ))}
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--color-ink)]">{item.snippet}</p>
            {!!item.path_sources?.length && (
              <div className="mt-2 text-xs text-[var(--color-ink-soft)]">
                来源: {item.path_sources.map(formatSource).join("；")}
              </div>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}
