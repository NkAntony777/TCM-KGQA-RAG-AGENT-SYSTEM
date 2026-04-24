"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  type SkillMeta,
  listSkills,
  setRagMode
} from "@/lib/api";
import { loadInitialAppState } from "@/lib/storeBootstrap";
import {
  buildEditableFiles,
  type AppStore
} from "@/lib/storeModels";
import { useInspectorState } from "@/lib/useInspectorState";
import { useSessionState } from "@/lib/useSessionState";

const StoreContext = createContext<AppStore | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [ragMode, setRagModeState] = useState(false);
  const [qaMode, setQaModeState] = useState<"quick" | "deep">("quick");
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [sidebarWidth, setSidebarWidth] = useState(308);
  const [inspectorWidth, setInspectorWidth] = useState(360);

  const editableFiles = useMemo(() => buildEditableFiles(skills), [skills]);

  async function refreshSkills() {
    setSkills(await listSkills());
  }

  const {
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    applyInspectorFile,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector
  } = useInspectorState({ refreshSkills });

  const {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    tokenStats,
    bootstrapSessions,
    createNewSession,
    selectSession,
    sendMessage,
    renameCurrentSession,
    removeSession,
    compressCurrentSession
  } = useSessionState({ qaMode });

  async function toggleRagMode() {
    const next = !ragMode;
    setRagModeState(next);
    try {
      await setRagMode(next);
    } catch (error) {
      setRagModeState(!next);
      throw error;
    }
  }

  useEffect(() => {
    void (async () => {
      try {
        const initialState = await loadInitialAppState();
        setRagModeState(initialState.ragMode);
        setSkills(initialState.skills);
        await bootstrapSessions(initialState.sessions);
        applyInspectorFile(initialState.inspectorFile);
      } catch (error) {
        console.error("Failed to bootstrap app state", error);
        setRagModeState(false);
        setSkills([]);
      }
    })();
  }, [applyInspectorFile, bootstrapSessions]);

  const value: AppStore = {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    ragMode,
    qaMode,
    skills,
    editableFiles,
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    sidebarWidth,
    inspectorWidth,
    tokenStats,
    createNewSession,
    selectSession,
    sendMessage,
    toggleRagMode,
    setQaMode: setQaModeState,
    renameCurrentSession,
    removeSession,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector,
    compressCurrentSession,
    setSidebarWidth,
    setInspectorWidth
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useAppStore() {
  const value = useContext(StoreContext);
  if (!value) {
    throw new Error("useAppStore must be used inside AppProvider");
  }
  return value;
}
