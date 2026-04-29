"use client";

import { useCallback, useRef, useState } from "react";
import { Network, Search } from "lucide-react";

import { GraphMiniMap } from "@/components/chat/GraphMiniMap";
import { getGraphSchemaSummary, getGraphSubgraph, type GraphVizPayload } from "@/lib/api";

const DEFAULT_SUBGRAPH_LIMIT = 120;

export function KnowledgeGraphPanel({
  embedded = false,
  onGraphMetaChange
}: {
  embedded?: boolean;
  onGraphMetaChange?: (meta: GraphVizPayload["meta"] | null) => void;
}) {
  const [entity, setEntity] = useState("小建中汤");
  const [depth, setDepth] = useState(2);
  const [limit, setLimit] = useState(DEFAULT_SUBGRAPH_LIMIT);
  const [graph, setGraph] = useState<GraphVizPayload | null>(null);
  const [schemaGraph, setSchemaGraph] = useState<GraphVizPayload | null>(null);
  const [mode, setMode] = useState<"subgraph" | "schema">("subgraph");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [paperMode, setPaperMode] = useState(true);
  const graphCacheRef = useRef(new Map<string, GraphVizPayload>());

  const loadSubgraph = useCallback(async (nextEntity = entity, nextDepth = depth) => {
    const trimmedEntity = nextEntity.trim();
    if (!trimmedEntity) {
      return;
    }
    const cacheKey = `subgraph:${trimmedEntity}:${nextDepth}:${limit}`;
    const cachedGraph = graphCacheRef.current.get(cacheKey);
    if (cachedGraph) {
      setGraph(cachedGraph);
      onGraphMetaChange?.(cachedGraph.meta);
      setMode("subgraph");
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const nextGraph = await getGraphSubgraph(trimmedEntity, nextDepth, limit);
      graphCacheRef.current.set(cacheKey, nextGraph);
      setGraph(nextGraph);
      onGraphMetaChange?.(nextGraph.meta);
      setMode("subgraph");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }, [depth, entity, limit, onGraphMetaChange]);

  const loadSchema = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      let nextSchemaGraph = schemaGraph;
      if (!schemaGraph) {
        nextSchemaGraph = await getGraphSchemaSummary();
        setSchemaGraph(nextSchemaGraph);
      }
      onGraphMetaChange?.(nextSchemaGraph?.meta ?? null);
      setMode("schema");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }, [onGraphMetaChange, schemaGraph]);

  const activeGraph = mode === "schema" ? schemaGraph : graph;
  const graphMeta = activeGraph?.meta;

  return (
    <section className={embedded ? "" : "panel rounded-[30px] p-5"}>
      <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-[var(--color-ink-soft)]">
            Knowledge Graph
          </p>
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-[-0.04em]">
            <Network size={18} />
            图谱子图
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            className={`rounded-full px-3 py-2 text-xs font-medium transition-colors ${
              mode === "subgraph" ? "bg-[var(--color-ink)] text-white" : "bg-white/70 text-[var(--color-ink)]"
            }`}
            onClick={() => graph ? setMode("subgraph") : void loadSubgraph(entity, depth)}
            type="button"
          >
            实体子图
          </button>
          <button
            className={`rounded-full px-3 py-2 text-xs font-medium transition-colors ${
              mode === "schema" ? "bg-[var(--color-ink)] text-white" : "bg-white/70 text-[var(--color-ink)]"
            }`}
            onClick={() => void loadSchema()}
            type="button"
          >
            Schema 总览
          </button>
          <button
            className="rounded-full bg-white/70 px-3 py-2 text-xs font-medium text-[var(--color-ink)] transition-colors"
            onClick={() => setPaperMode((value) => !value)}
            type="button"
          >
            {paperMode ? "论文模式" : "探索模式"}
          </button>
        </div>
      </div>

      {mode === "subgraph" && (
        <form
          className="mb-4 flex flex-col gap-2 md:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void loadSubgraph(entity, depth);
          }}
        >
          <label className="flex min-w-0 flex-1 items-center gap-2 rounded-2xl bg-white/75 px-3 py-2">
            <Search size={16} className="text-[var(--color-ink-soft)]" />
            <input
              className="min-w-0 flex-1 bg-transparent text-sm outline-none"
              onChange={(event) => setEntity(event.target.value)}
              placeholder="输入方剂、药材、证候或疾病"
              value={entity}
            />
          </label>
          <select
            className="rounded-2xl bg-white/75 px-3 py-2 text-sm outline-none"
            onChange={(event) => setDepth(Number(event.target.value))}
            value={depth}
          >
            <option value={1}>1-hop 精简</option>
            <option value={2}>2-hop 扩展</option>
          </select>
          <select
            className="rounded-2xl bg-white/75 px-3 py-2 text-sm outline-none"
            onChange={(event) => setLimit(Number(event.target.value))}
            value={limit}
          >
            <option value={80}>80 节点</option>
            <option value={120}>120 节点</option>
            <option value={160}>160 节点</option>
            <option value={200}>200 节点</option>
          </select>
          <button
            className="rounded-2xl bg-[var(--color-ember)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            disabled={loading}
            type="submit"
          >
            {loading ? "加载中" : graph ? "重新生成" : "加载示例子图"}
          </button>
        </form>
      )}

      {error && (
        <div className="mb-4 rounded-2xl bg-[rgba(194,87,87,0.12)] p-3 text-sm text-[var(--color-ink)]">
          {error}
        </div>
      )}

      {activeGraph ? (
        <div className={paperMode ? "rounded-[28px] bg-[#F6F3EA] p-3" : ""}>
          <GraphMiniMap graph={activeGraph} compact={paperMode && activeGraph.nodes.length > 80} height={paperMode ? 560 : 660} />
          {!paperMode && (
            <div className="mt-3 grid gap-2 text-xs text-[var(--color-ink-soft)] md:grid-cols-3">
              <div className="rounded-2xl bg-white/70 p-3">节点: {activeGraph.nodes.length}</div>
              <div className="rounded-2xl bg-white/70 p-3">边: {activeGraph.edges.length}</div>
              <div className="rounded-2xl bg-white/70 p-3">
                后端: {graphMeta?.graph_backend ?? graphMeta?.kind ?? "local"}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-3xl border border-dashed border-[var(--color-line)] bg-white/50 p-6 text-sm text-[var(--color-ink-soft)]">
          图谱不会随页面进入自动加载。默认使用 2-hop 扩展视图，默认展示 {DEFAULT_SUBGRAPH_LIMIT} 个节点，可切换到 200 节点进行探索。
        </div>
      )}
    </section>
  );
}
