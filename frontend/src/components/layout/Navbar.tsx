"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import dynamic from "next/dynamic";
import { Database, FileStack, Network, Plus, Sparkles, Wrench, X } from "lucide-react";

import type { GraphVizPayload } from "@/lib/api";
import { useAppStore } from "@/lib/store";

const KnowledgeGraphPanel = dynamic(
  () => import("@/components/chat/KnowledgeGraphPanel").then((module) => module.KnowledgeGraphPanel),
  {
    loading: () => (
      <div className="rounded-3xl border border-dashed border-[var(--color-line)] bg-white/55 p-8 text-sm text-[var(--color-ink-soft)]">
        正在加载知识图谱交互组件...
      </div>
    ),
    ssr: false
  }
);

export function Navbar() {
  const [showGraphPanel, setShowGraphPanel] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [graphMeta, setGraphMeta] = useState<GraphVizPayload["meta"] | null>(null);
  const {
    createNewSession,
    ragMode,
    toggleRagMode,
    compressCurrentSession,
    renameCurrentSession,
    sessions,
    currentSessionId
  } = useAppStore();

  const currentTitle =
    sessions.find((session) => session.id === currentSessionId)?.title ?? "新会话";

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!showGraphPanel) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [showGraphPanel]);

  const formatGraphCount = (value?: number) => {
    if (value === undefined || value === null) {
      return "加载后显示";
    }
    return new Intl.NumberFormat("zh-CN").format(value);
  };

  const graphModal = showGraphPanel ? (
    <div className="fixed inset-0 z-[9999] bg-[rgba(13,37,48,0.28)] p-4 backdrop-blur-sm md:p-8">
      <div className="mx-auto flex max-h-[calc(100vh-4rem)] max-w-6xl flex-col overflow-hidden rounded-[34px] border border-white/70 bg-[#F7F4EC] shadow-2xl">
        <div className="flex items-center justify-between gap-4 border-b border-[var(--color-line)] px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-[var(--color-ink-soft)]">
              On-demand Graph
            </p>
            <h2 className="text-xl font-semibold tracking-[-0.04em]">知识图谱可视化</h2>
          </div>
          <div className="ml-auto hidden items-center gap-2 lg:flex">
            <div className="rounded-2xl bg-white/70 px-4 py-2 text-xs">
              <span className="mr-2 text-[var(--color-ink-soft)]">实体</span>
              <strong>{formatGraphCount(graphMeta?.graph_node_count)}</strong>
            </div>
            <div className="rounded-2xl bg-white/70 px-4 py-2 text-xs">
              <span className="mr-2 text-[var(--color-ink-soft)]">关系</span>
              <strong>{formatGraphCount(graphMeta?.graph_edge_count)}</strong>
            </div>
            <div className="rounded-2xl bg-white/70 px-4 py-2 text-xs">
              <span className="mr-2 text-[var(--color-ink-soft)]">证据</span>
              <strong>{formatGraphCount(graphMeta?.graph_evidence_count)}</strong>
            </div>
          </div>
          <button
            aria-label="关闭知识图谱"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white/80 text-[var(--color-ink)] transition-colors hover:bg-white"
            onClick={() => setShowGraphPanel(false)}
            type="button"
          >
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto p-6">
          <KnowledgeGraphPanel embedded onGraphMetaChange={setGraphMeta} />
        </div>
      </div>
    </div>
  ) : null;

  return (
    <header className="panel flex items-center justify-between rounded-[30px] px-5 py-4">
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[rgba(15,139,141,0.14)] text-ocean">
          <Sparkles size={20} />
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-[var(--color-ink-soft)]">
            TCM—Agent
          </p>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-[-0.04em]">{currentTitle}</h1>
            <button
              className="rounded-full border border-[var(--color-line)] px-3 py-1 text-xs text-[var(--color-ink-soft)]"
              onClick={() => {
                const next = window.prompt("重命名当前会话", currentTitle);
                if (next) {
                  void renameCurrentSession(next);
                }
              }}
              type="button"
            >
              Rename
            </button>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          className="flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white/60 px-4 py-2 text-sm transition-colors hover:bg-white"
          onClick={() => setShowGraphPanel(true)}
          type="button"
        >
          <Network size={16} />
          知识图谱
        </button>
        <button
          className="flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white/60 px-4 py-2 text-sm"
          onClick={() => void createNewSession()}
          type="button"
        >
          <Plus size={16} />
          新会话
        </button>
        <button
          className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm ${
            ragMode
              ? "bg-ocean text-white"
              : "border border-[var(--color-line)] bg-white/60 text-ink"
          }`}
          onClick={() => void toggleRagMode()}
          type="button"
        >
          <Database size={16} />
          {ragMode ? "RAG 已开" : "RAG 已关"}
        </button>
        <button
          className="flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white/60 px-4 py-2 text-sm"
          onClick={() => void compressCurrentSession()}
          type="button"
        >
          <Wrench size={16} />
          压缩
        </button>
        <div className="hidden items-center gap-2 rounded-full bg-[rgba(212,106,74,0.12)] px-4 py-2 text-sm text-[var(--color-ember)] md:flex">
          <FileStack size={16} />
          File-first Memory
        </div>
      </div>

      {mounted && graphModal ? createPortal(graphModal, document.body) : null}
    </header>
  );
}
