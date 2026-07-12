"use client";

import { useEffect, useMemo, useState } from "react";

import type { GraphVizEdge, GraphVizNode, GraphVizPayload } from "@/lib/api";
import { GraphChart } from "./GraphChart";
import { GraphSidebar } from "./GraphSidebar";

const TYPE_COLORS: Record<string, string> = {
  formula: "#2F6F73",
  herb: "#6A8D3A",
  syndrome: "#B06A35",
  symptom: "#C25757",
  disease: "#8E5D9F",
  therapy: "#D09A33",
  book: "#4F6FA8",
  chapter: "#6E7D91",
  property: "#7B8F3A",
  channel: "#3D8C8C",
  food: "#C77A46",
  category: "#8A7654",
  processing_method: "#9A6B3A",
  other: "#6B7280"
};

function colorFor(type: string) {
  return TYPE_COLORS[type] ?? TYPE_COLORS.other;
}

function visibleLabelLimit(nodeCount: number, compact: boolean, schemaMode: boolean) {
  if (schemaMode) {
    return nodeCount;
  }
  if (nodeCount <= 80) {
    return compact ? 34 : 48;
  }
  if (nodeCount <= 140) {
    return compact ? 42 : 64;
  }
  return compact ? 48 : 76;
}

function nodeScore(node: GraphVizNode, degreeMap: Map<string, number>) {
  return (
    (node.evidence_count ?? 1) +
    (node.source_count ?? 0) * 2 +
    (degreeMap.get(node.id) ?? 0) * 1.5 +
    (node.is_center ? 1000 : 0)
  );
}

export function GraphMiniMap({
  graph,
  height = 320,
  compact = false
}: {
  graph: GraphVizPayload;
  height?: number;
  compact?: boolean;
}) {
  const [dragMode, setDragMode] = useState<"pan" | "node">("pan");
  const [selectedNode, setSelectedNode] = useState<GraphVizNode | null>(
    graph.nodes.find((node) => node.is_center) ?? graph.nodes[0] ?? null
  );
  const [selectedEdge, setSelectedEdge] = useState<GraphVizEdge | null>(null);

  const degreeMap = useMemo(() => {
    const nextDegreeMap = new Map<string, number>();
    graph.edges.forEach((edge) => {
      nextDegreeMap.set(edge.source, (nextDegreeMap.get(edge.source) ?? 0) + 1);
      nextDegreeMap.set(edge.target, (nextDegreeMap.get(edge.target) ?? 0) + 1);
    });
    return nextDegreeMap;
  }, [graph.edges]);

  const labelIds = useMemo(() => {
    const ids = new Set<string>();
    const labelLimit = visibleLabelLimit(graph.nodes.length, compact, graph.meta.kind === "schema");
    graph.nodes
      .slice()
      .sort((left, right) => nodeScore(right, degreeMap) - nodeScore(left, degreeMap))
      .slice(0, labelLimit)
      .forEach((node) => ids.add(node.id));
    return ids;
  }, [compact, degreeMap, graph.meta.kind, graph.nodes]);

  const legend = useMemo(() => {
    return Array.from(new Map(graph.nodes.map((node) => [node.type, node.type_label ?? node.type])).entries());
  }, [graph.nodes]);

  useEffect(() => {
    setSelectedNode(graph.nodes.find((node) => node.is_center) ?? graph.nodes[0] ?? null);
    setSelectedEdge(null);
  }, [graph]);

  const handleNodeClick = (node: GraphVizNode) => {
    setSelectedNode(node);
    setSelectedEdge(null);
  };

  const handleEdgeClick = (edge: GraphVizEdge) => {
    setSelectedEdge(edge);
  };

  return (
    <div className="overflow-hidden rounded-3xl border border-[var(--color-line)] bg-white/70" style={{ overscrollBehavior: "contain" }}>
      <div className="grid items-start gap-0 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-line)] px-4 py-3 text-xs text-[var(--color-ink-soft)]">
            <div className="flex flex-wrap items-center gap-2">
              <span>滚轮缩放 / 拖拽平移 / 点击节点查看元信息</span>
              <button
                className={`rounded-full px-2 py-1 transition-colors ${
                  dragMode === "pan" ? "bg-[var(--color-ink)] text-white" : "bg-white/80 text-[var(--color-ink-soft)]"
                }`}
                onClick={() => setDragMode("pan")}
                type="button"
              >
                平移画布
              </button>
              <button
                className={`rounded-full px-2 py-1 transition-colors ${
                  dragMode === "node" ? "bg-[var(--color-ink)] text-white" : "bg-white/80 text-[var(--color-ink-soft)]"
                }`}
                onClick={() => setDragMode("node")}
                type="button"
              >
                拖拽节点
              </button>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {!compact && legend.slice(0, 5).map(([type, label]) => (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-1" key={type}>
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: colorFor(type) }} />
                  {label}
                </span>
              ))}
              <span>
                节点 {graph.nodes.length} · 边 {graph.edges.length} · {graph.meta.depth}-hop
              </span>
            </div>
          </div>
          <GraphChart
            nodes={graph.nodes}
            edges={graph.edges}
            compact={compact}
            dragMode={dragMode}
            labelIds={labelIds}
            metaKind={graph.meta.kind ?? ""}
            height={height}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
          />
        </div>
        <GraphSidebar
          edges={graph.edges}
          selectedNode={selectedNode}
          selectedEdge={selectedEdge}
          onEdgeClick={handleEdgeClick}
          height={height}
        />
      </div>
    </div>
  );
}
