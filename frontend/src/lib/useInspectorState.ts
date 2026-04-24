"use client";

import { useCallback, useState } from "react";

import { loadFile, saveFile } from "@/lib/api";

export type InspectorFile = {
  path: string;
  content: string;
};

export function useInspectorState({ refreshSkills }: { refreshSkills: () => Promise<void> }) {
  const [inspectorPath, setInspectorPath] = useState("memory/MEMORY.md");
  const [inspectorContent, setInspectorContent] = useState("");
  const [inspectorDirty, setInspectorDirty] = useState(false);

  const applyInspectorFile = useCallback((file: InspectorFile) => {
    setInspectorPath(file.path);
    setInspectorContent(file.content);
    setInspectorDirty(false);
  }, []);

  async function loadInspectorFile(path: string) {
    applyInspectorFile(await loadFile(path));
  }

  function updateInspectorContent(value: string) {
    setInspectorContent(value);
    setInspectorDirty(true);
  }

  async function saveInspector() {
    await saveFile(inspectorPath, inspectorContent);
    setInspectorDirty(false);
    await refreshSkills();
  }

  return {
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    applyInspectorFile,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector
  };
}
