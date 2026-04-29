"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts";
import type { ECharts, EChartsOption } from "echarts";

import type { GraphVizEdge, GraphVizNode, GraphVizPayload } from "@/lib/api";

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

function shortLabel(label: string, max = 8) {
  return label.length > max ? `${label.slice(0, max)}...` : label;
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

function escapeHtml(value: unknown) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function nodeScore(node: GraphVizNode, degreeMap: Map<string, number>) {
  return (
    (node.evidence_count ?? 1) +
    (node.source_count ?? 0) * 2 +
    (degreeMap.get(node.id) ?? 0) * 1.5 +
    (node.is_center ? 1000 : 0)
  );
}

function nodeSize(node: GraphVizNode) {
  if (node.is_center) {
    return 54;
  }
  if (node.is_schema) {
    return 40;
  }
  const count = Math.max(1, node.evidence_count ?? 1);
  return Math.min(34, 16 + Math.log2(count + 1) * 3.1);
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

type GraphTooltipParams = {
  data?: Partial<GraphVizNode & GraphVizEdge> & {
    display_label?: string;
    name?: string;
  };
  dataType?: string;
};

type ChartNodeData = Omit<GraphVizNode, "label"> & {
  display_label: string;
  label?: unknown;
  name?: string;
};

function toGraphNode(data: Partial<ChartNodeData> | undefined): GraphVizNode | null {
  if (!data?.id) {
    return null;
  }
  return {
    id: String(data.id),
    label: String(data.display_label ?? data.name ?? data.id),
    type: String(data.type ?? "other"),
    type_label: data.type_label,
    score: data.score,
    evidence_count: data.evidence_count,
    source_count: data.source_count,
    is_center: data.is_center,
    is_schema: data.is_schema
  };
}

function buildCategories(nodes: GraphVizNode[]) {
  return Array.from(new Map(nodes.map((node) => [node.type, node.type_label ?? node.type])).entries())
    .map(([type, label]) => ({
      name: label,
      itemStyle: { color: colorFor(type) }
    }));
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
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<ECharts | null>(null);
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

  const incidentEdges = useMemo(() => {
    if (!selectedNode) {
      return [];
    }
    return graph.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id);
  }, [graph.edges, selectedNode]);

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

  const legend = useMemo(() => {
    return Array.from(new Map(graph.nodes.map((node) => [node.type, node.type_label ?? node.type])).entries());
  }, [graph.nodes]);

  useEffect(() => {
    setSelectedNode(graph.nodes.find((node) => node.is_center) ?? graph.nodes[0] ?? null);
    setSelectedEdge(null);
  }, [graph]);

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    const chartElement = chartRef.current;
    const chart = echarts.init(chartElement, undefined, { renderer: "canvas" });
    chartInstanceRef.current = chart;

    const categories = buildCategories(graph.nodes);
    const categoryIndex = new Map(categories.map((category, index) => [category.name, index]));
    const option: EChartsOption = {
      animationDurationUpdate: 700,
      backgroundColor: "transparent",
      tooltip: {
        confine: true,
        formatter: (rawParams) => {
          const params = (Array.isArray(rawParams) ? rawParams[0] : rawParams) as GraphTooltipParams;
          const data = params.data;
          if (!data) {
            return "";
          }
          if (params.dataType === "edge") {
            return `<strong>${escapeHtml(data.predicate)}</strong><br/>${escapeHtml(data.source)} -> ${escapeHtml(data.target)}<br/>证据数: ${escapeHtml(data.evidence_count ?? 0)}`;
          }
          return `<strong>${escapeHtml(data.display_label ?? data.name ?? data.id)}</strong><br/>类型: ${escapeHtml(data.type_label ?? data.type)}<br/>证据数: ${escapeHtml(data.evidence_count ?? 0)}<br/>来源数: ${escapeHtml(data.source_count ?? 0)}`;
        }
      },
      series: [
        {
          type: "graph",
          layout: "force",
          categories,
          data: graph.nodes.map((node) => ({
            id: node.id,
            display_label: node.label,
            type: node.type,
            type_label: node.type_label,
            score: node.score,
            evidence_count: node.evidence_count,
            source_count: node.source_count,
            is_center: node.is_center,
            is_schema: node.is_schema,
            name: node.label,
            category: categoryIndex.get(node.type_label ?? node.type) ?? 0,
            draggable: dragMode === "node",
            symbolSize: nodeSize(node),
            itemStyle: {
              borderColor: "#FFFFFF",
              borderWidth: node.is_center ? 4 : 2,
              color: colorFor(node.type)
            },
            label: {
              show: labelIds.has(node.id),
              color: "#0D2530",
              formatter: shortLabel(node.label, node.is_center ? 14 : 10),
              fontSize: node.is_center ? 15 : 11,
              fontWeight: node.is_center ? 700 : 600,
              position: "right",
              backgroundColor: "rgba(255,255,255,0.78)",
              borderRadius: 6,
              padding: [2, 4]
            },
            emphasis: {
              label: {
                show: true,
                formatter: node.label
              }
            }
          })),
          links: graph.edges.map((edge) => ({
            ...edge,
            name: edge.predicate,
            value: edge.evidence_count ?? 1,
            lineStyle: {
              color: "#8CA0A6",
              curveness: 0.12,
              opacity: compact ? 0.34 : 0.5,
              width: Math.min(4, 1 + Math.log2((edge.evidence_count ?? 1) + 1) * 0.35)
            },
            label: {
              show: !compact,
              color: "#465A62",
              formatter: shortLabel(edge.predicate, 8),
              fontSize: 10
            }
          })),
          edgeLabel: {
            show: !compact
          },
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: [0, 8],
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              opacity: 0.9,
              width: 3
            }
          },
          force: {
            edgeLength: graph.meta.kind === "schema" ? 150 : [120, 260],
            friction: 0.34,
            gravity: graph.meta.kind === "schema" ? 0.08 : 0.04,
            repulsion: compact ? 520 : 900
          },
          roam: true,
          scaleLimit: {
            min: 0.25,
            max: 6
          },
          selectedMode: "single"
        }
      ]
    };

    chart.setOption(option);
    chart.on("click", (params) => {
      if (params.dataType === "node") {
        const nextNode = toGraphNode(params.data as ChartNodeData);
        if (nextNode) {
          setSelectedNode(nextNode);
          setSelectedEdge(null);
        }
      }
      if (params.dataType === "edge") {
        setSelectedEdge(params.data as GraphVizEdge);
      }
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    chart.getZr().on("mousewheel", (event) => {
      event.event?.preventDefault();
      event.event?.stopPropagation();
    });
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.getZr().off("mousewheel");
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [compact, degreeMap, dragMode, graph, height, labelIds]);

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
          <div ref={chartRef} className="touch-none" style={{ height, overscrollBehavior: "contain" }} />
        </div>
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
                      onClick={() => setSelectedEdge(edge)}
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
      </div>
    </div>
  );
}
