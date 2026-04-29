"use client";

import { useState } from "react";
import Editor from "@monaco-editor/react";
import { Eye, Pencil, Save } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useAppStore } from "@/lib/store";

export function InspectorPanel() {
  const [previewMode, setPreviewMode] = useState(true);
  const {
    editableFiles,
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector
  } = useAppStore();

  return (
    <aside className="panel flex h-full flex-col rounded-[30px] p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-[var(--color-ink-soft)]">
            Inspector
          </p>
          <h2 className="text-lg font-semibold tracking-[-0.04em]">Memory / Skills / Prompt</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white/60 px-3 py-2 text-sm text-[var(--color-ink-soft)] transition-colors hover:bg-white"
            onClick={() => setPreviewMode((value) => !value)}
            type="button"
          >
            {previewMode ? <Pencil size={16} /> : <Eye size={16} />}
            {previewMode ? "编辑" : "预览"}
          </button>
          <button
            className="flex items-center gap-2 rounded-full bg-[rgba(15,139,141,0.12)] px-4 py-2 text-sm text-ocean"
            onClick={() => void saveInspector()}
            type="button"
          >
            <Save size={16} />
            {inspectorDirty ? "保存修改" : "已同步"}
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {editableFiles.map((path) => (
          <button
            className={`rounded-full px-3 py-1 text-xs ${
              path === inspectorPath
                ? "bg-[rgba(13,37,48,0.92)] text-white"
                : "border border-[var(--color-line)] bg-white/55 text-[var(--color-ink-soft)]"
            }`}
            key={path}
            onClick={() => void loadInspectorFile(path)}
            type="button"
          >
            {path}
          </button>
        ))}
      </div>

      <div className="min-h-0 overflow-hidden rounded-[26px] border border-[var(--color-line)] bg-white/65">
        {previewMode ? (
          <div className="markdown inspector-markdown h-[calc(100vh-270px)] overflow-y-auto px-5 py-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {inspectorContent || "当前文件为空。"}
            </ReactMarkdown>
          </div>
        ) : (
          <Editor
            defaultLanguage="markdown"
            height="calc(100vh - 270px)"
            onChange={(value) => updateInspectorContent(value ?? "")}
            options={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              lineNumbersMinChars: 3,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              wordWrap: "on"
            }}
            path={inspectorPath}
            theme="vs-light"
            value={inspectorContent}
          />
        )}
      </div>
    </aside>
  );
}
