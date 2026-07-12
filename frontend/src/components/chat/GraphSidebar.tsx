"use client";

import { useMemo } from "react";

import type { GraphVizEdge, GraphVizNode } from "@/lib/api";

function shortLabel(label: string, max = 8) {
  return label.length > max ? `${label.slice(0, max)}...` : label;
}

function relationSummary(edge: GraphVizEdge) {
  const sourceBooks = edge.source_books?.slice(0, 3).join("、") || "暂无";
  return [
    `关系: ${edge.predicate}`,
    `方向: ${edge.source} -> ${edge.target}`,
    `证据数: ${edge.evidence_count ?? 0}`,
    `来源: ${sourceBooks}`
  ];
}

export interface GraphSidebarProps {
  edges: GraphVizEdge[];
  selectedNode: GraphVizNode | null;
  selectedEdge: GraphVizEdge | null;
  onEdgeClick: (edge: GraphVizEdge) => void;
  height: number;
}

export function GraphSidebar({
  edges,
  selectedNode,
  selectedEdge,
  onEdgeClick,
  height
}: GraphSidebarProps) {
  const incidentEdges = useMemo(() => {
    if (!selectedNode) {
      return [];
    }
    return edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id);
  }, [edges, selectedNode]);

  const selectedStats = useMemo(() => {
    const sourceBooks = new Set<string>();
    const edgeEvidenceTotal = incidentEdges.reduce((total, edge) => {
      edge.source_books?.forEach((book) => {
        if (book) {
          sourceBooks.add(book);
        }
      });
      return total + (edge.evidence_count ?? 0);
    }, 0);
    return {
      degree: incidentEdges.length,
      evidenceCount: selectedNode?.evidence_count || edgeEvidenceTotal,
      sourceCount: selectedNode?.source_count || sourceBooks.size
    };
  }, [incidentEdges, selectedNode]);

  return (
    <aside
      className="overflow-y-auto border-t border-[var(--color-line)] bg-[#F8F5ED] p-4 text-sm xl:border-l xl:border-t-0"
      style={{ maxHeight: height + 49, overscrollBehavior: "contain" }}
    >
      <p className="text-xs uppercase tracking-[0.24em] text-[var(--color-ink-soft)]">
        Selection
      </p>
      {selectedNode ? (
        <div className="mt-3 space-y-3">
          <div>
            <h3 className="text-lg font-semibold tracking-[-0.04em]">{selectedNode.label}</h3>
            <p className="mt-1 text-xs text-[var(--color-ink-soft)]">
              {selectedNode.type_label ?? selectedNode.type} · ID: {selectedNode.id}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-2xl bg-white/75 p-3">证据数: {selectedStats.evidenceCount}</div>
            <div className="rounded-2xl bg-white/75 p-3">来源数: {selectedStats.sourceCount}</div>
            <div className="col-span-2 rounded-2xl bg-white/75 p-3">关联边数: {selectedStats.degree}</div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold text-[var(--color-ink-soft)]">关联关系</p>
            <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
              {incidentEdges.slice(0, 10).map((edge, index) => (
                <button
                  className="block w-full rounded-2xl bg-white/70 p-3 text-left text-xs transition-colors hover:bg-white"
                  key={`${edge.source}-${edge.target}-${edge.predicate}-${index}`}
                  onClick={() => onEdgeClick(edge)}
                  type="button"
                >
                  <span className="font-semibold">{edge.predicate}</span>
                  <span className="mt-1 block text-[var(--color-ink-soft)]">
                    {shortLabel(edge.source, 8)} {"->"} {shortLabel(edge.target, 8)}
                  </span>
                </button>
              ))}
              {!incidentEdges.length && (
                <div className="rounded-2xl bg-white/70 p-3 text-xs text-[var(--color-ink-soft)]">
                  暂无关联边。
                </div>
              )}
            </div>
          </div>
          {selectedEdge && (
            <div className="rounded-2xl bg-[rgba(15,139,141,0.08)] p-3 text-xs">
              {relationSummary(selectedEdge).map((line) => (
                <p className="mb-1 last:mb-0" key={line}>{line}</p>
              ))}
              {selectedEdge.source_text && (
                <p className="mt-2 leading-5 text-[var(--color-ink-soft)]">
                  {selectedEdge.source_text}
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-3 rounded-2xl bg-white/70 p-3 text-xs text-[var(--color-ink-soft)]">
          点击图中的节点查看详情。
        </div>
      )}
    </aside>
  );
}
