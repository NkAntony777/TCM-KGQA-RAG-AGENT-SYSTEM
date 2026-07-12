"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { ECharts, EChartsOption } from "echarts";

import type { GraphVizEdge, GraphVizNode } from "@/lib/api";

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

function escapeHtml(value: unknown) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildCategories(nodes: GraphVizNode[]) {
  return Array.from(new Map(nodes.map((node) => [node.type, node.type_label ?? node.type])).entries())
    .map(([type, label]) => ({
      name: label,
      itemStyle: { color: colorFor(type) }
    }));
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

export interface GraphChartProps {
  nodes: GraphVizNode[];
  edges: GraphVizEdge[];
  compact: boolean;
  dragMode: "pan" | "node";
  labelIds: Set<string>;
  metaKind: string;
  height: number;
  onNodeClick: (node: GraphVizNode) => void;
  onEdgeClick: (edge: GraphVizEdge) => void;
}

export function GraphChart({
  nodes,
  edges,
  compact,
  dragMode,
  labelIds,
  metaKind,
  height,
  onNodeClick,
  onEdgeClick
}: GraphChartProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<ECharts | null>(null);

  const onNodeClickRef = useRef(onNodeClick);
  const onEdgeClickRef = useRef(onEdgeClick);
  onNodeClickRef.current = onNodeClick;
  onEdgeClickRef.current = onEdgeClick;

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    const chartElement = chartRef.current;
    const chart = echarts.init(chartElement, undefined, { renderer: "canvas" });
    chartInstanceRef.current = chart;

    const categories = buildCategories(nodes);
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
          data: nodes.map((node) => ({
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
          links: edges.map((edge) => ({
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
            edgeLength: metaKind === "schema" ? 150 : [120, 260],
            friction: 0.34,
            gravity: metaKind === "schema" ? 0.08 : 0.04,
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
          onNodeClickRef.current(nextNode);
        }
      }
      if (params.dataType === "edge") {
        onEdgeClickRef.current(params.data as GraphVizEdge);
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
  }, [compact, dragMode, edges, height, labelIds, metaKind, nodes]);

  return <div ref={chartRef} className="touch-none" style={{ height, overscrollBehavior: "contain" }} />;
}
