"use client";

import { BookOpenText } from "lucide-react";

import type { EvidenceItem } from "@/lib/api";

function formatSource(item: EvidenceItem) {
  const book = item.source_book?.trim();
  const chapter = item.source_chapter?.trim();
  if (book && chapter) {
    return `《${book}》 ${chapter}`;
  }
  if (book) {
    return `《${book}》`;
  }
  if (chapter) {
    return chapter;
  }
  return item.source;
}

function formatScore(item: EvidenceItem) {
  const value = item.confidence ?? item.score;
  return value == null ? "n/a" : value.toFixed(3);
}

export function EvidenceCard({ items }: { items: EvidenceItem[] }) {
  const plainItems = items.filter((item) => item.source_type !== "graph_path");
  if (!plainItems.length) {
    return null;
  }

  return (
    <details className="mb-4 rounded-3xl border border-[rgba(67,138,85,0.18)] bg-[rgba(67,138,85,0.08)] p-4" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-[var(--color-ink)]">
        <BookOpenText size={16} />
        证据 {plainItems.length} 条
      </summary>
      <div className="mt-3 space-y-3">
        {plainItems.map((item, index) => {
          const relationText = item.predicate && item.target ? `${item.predicate}: ${item.target}` : "";
          const sourceText = item.source_text?.trim() || item.snippet;
          const sourceLabel = item.source_type === "graph" ? formatSource(item) : `[${item.source_type}] ${item.source}`;

          return (
            <div className="rounded-2xl bg-white/70 p-3" key={`${item.source}-${item.fact_id ?? index}`}>
              <div className="mb-1 flex items-center justify-between gap-3 text-xs text-[var(--color-ink-soft)]">
                <span>{sourceLabel}</span>
                <span>{formatScore(item)}</span>
              </div>
              {relationText ? (
                <div className="mb-2 text-xs font-medium text-[var(--color-ink-soft)]">{relationText}</div>
              ) : null}
              <p className="text-sm leading-6 text-[var(--color-ink)]">{sourceText}</p>
            </div>
          );
        })}
      </div>
    </details>
  );
}
