"use client";

import { Network } from "lucide-react";

import { GraphMiniMap } from "@/components/chat/GraphMiniMap";
import type { EvidenceItem, GraphVizEdge, GraphVizNode, GraphVizPayload } from "@/lib/api";

function inferNodeType(label: string) {
  if (label.includes("汤") || label.includes("丸") || label.includes("散") || label.includes("方")) {
    return "formula";
  }
  if (label.includes("证")) {
    return "syndrome";
  }
  return "other";
}

function addNode(nodes: Map<string, GraphVizNode>, id: string, type?: string, extra?: Partial<GraphVizNode>) {
  if (!id.trim()) {
    return;
  }
  const existing = nodes.get(id);
  nodes.set(id, {
    ...existing,
    ...extra,
    id,
    label: id,
    type: type || existing?.type || inferNodeType(id),
    type_label: existing?.type_label,
    evidence_count: (existing?.evidence_count ?? 0) + (extra?.evidence_count ?? 1)
  });
}

function buildEvidenceGraph(items: EvidenceItem[]): GraphVizPayload | null {
  const graphItems = items.filter((item) => item.source_type === "graph" || item.source_type === "graph_path");
  if (!graphItems.length) {
    return null;
  }

  const nodes = new Map<string, GraphVizNode>();
  const edges = new Map<string, GraphVizEdge>();
  let center = "";

  for (const item of graphItems) {
    if (item.source_type === "graph_path" && item.path_nodes?.length) {
      const pathNodes = item.path_nodes;
      center ||= pathNodes[0];
      pathNodes.forEach((node, index) => {
        addNode(nodes, node, undefined, { is_center: node === center || (!center && index === 0) });
      });
      pathNodes.slice(0, -1).forEach((node, index) => {
        const target = pathNodes[index + 1];
        const predicate = item.path_edges?.[index] ?? "关联";
        edges.set(`${node}->${target}:${predicate}`, {
          source: node,
          target,
          predicate,
          evidence_count: 1,
          source_books: item.path_sources?.map((source) => source.source_book || "").filter(Boolean)
        });
      });
      continue;
    }

    const sourceEntity = item.document || item.source_book || item.source;
    const target = item.target?.trim();
    if (!target || !item.predicate) {
      continue;
    }
    center ||= sourceEntity;
    addNode(nodes, sourceEntity, inferNodeType(sourceEntity), { is_center: sourceEntity === center });
    addNode(nodes, target, undefined, { evidence_count: 1 });
    edges.set(`${sourceEntity}->${target}:${item.predicate}`, {
      source: sourceEntity,
      target,
      predicate: item.predicate,
      confidence: item.confidence,
      source_text: item.source_text || item.snippet,
      evidence_count: 1,
      source_books: item.source_book ? [item.source_book] : []
    });
  }

  if (!nodes.size || !edges.size) {
    return null;
  }

  return {
    nodes: Array.from(nodes.values()).slice(0, 36),
    edges: Array.from(edges.values()).slice(0, 60),
    meta: {
      kind: "evidence",
      center,
      depth: 1,
      truncated: nodes.size > 36 || edges.size > 60,
      node_total_before_limit: nodes.size,
      edge_total_before_limit: edges.size
    }
  };
}

export function GraphEvidenceView({ items }: { items: EvidenceItem[] }) {
  const graph = buildEvidenceGraph(items);
  if (!graph) {
    return null;
  }

  return (
    <details className="mb-4 rounded-3xl border border-[rgba(47,111,115,0.2)] bg-[rgba(47,111,115,0.08)] p-4" open>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-[var(--color-ink)]">
        <Network size={16} />
        本次回答证据子图
      </summary>
      <div className="mt-3 space-y-3">
        <GraphMiniMap graph={graph} compact={graph.nodes.length > 24} />
        <div className="rounded-2xl bg-white/70 p-3 text-xs text-[var(--color-ink-soft)]">
          该图仅展示本次回答实际使用的图谱路径和关系证据，不代表全量知识图谱。
          {graph.meta.truncated ? " 子图已按论文展示尺度截断。" : ""}
        </div>
      </div>
    </details>
  );
}
