"use client";

import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";

import { loadFile } from "@/lib/api";
import { buildEditableFiles } from "@/lib/storeModels";
import { useInspectorState, type InspectorFile } from "@/lib/useInspectorState";
import { useLayoutContext } from "@/lib/LayoutContext";

type InspectorContextValue = {
  editableFiles: string[];
  inspectorPath: string;
  inspectorContent: string;
  inspectorDirty: boolean;
  loadInspectorFile: (path: string) => Promise<void>;
  updateInspectorContent: (value: string) => void;
  saveInspector: () => Promise<void>;
};

const InspectorContext = createContext<InspectorContextValue | null>(null);

export function InspectorProvider({ children }: { children: ReactNode }) {
  const { skills, refreshSkills } = useLayoutContext();

  const editableFiles = useMemo(() => buildEditableFiles(skills), [skills]);

  const {
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    applyInspectorFile,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector
  } = useInspectorState({ refreshSkills });

  useEffect(() => {
    loadFile("memory/MEMORY.md")
      .then((file: InspectorFile) => applyInspectorFile(file))
      .catch((error) => console.error("Failed to bootstrap inspector", error));
  }, [applyInspectorFile]);

  const value: InspectorContextValue = {
    editableFiles,
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector
  };

  return <InspectorContext.Provider value={value}>{children}</InspectorContext.Provider>;
}

export function useInspectorContext() {
  const value = useContext(InspectorContext);
  if (!value) {
    throw new Error("useInspectorContext must be used inside AppProvider");
  }
  return value;
}

export { InspectorContext };
