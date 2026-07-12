"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { type SkillMeta, getRagMode, listSkills, setRagMode } from "@/lib/api";

type LayoutContextValue = {
  ragMode: boolean;
  qaMode: "quick" | "deep";
  fullEvidenceMode: boolean;
  skills: SkillMeta[];
  sidebarWidth: number;
  inspectorWidth: number;
  setFullEvidenceMode: (enabled: boolean) => void;
  setQaMode: (mode: "quick" | "deep") => void;
  toggleRagMode: () => Promise<void>;
  refreshSkills: () => Promise<void>;
  setSidebarWidth: (width: number) => void;
  setInspectorWidth: (width: number) => void;
};

const LayoutContext = createContext<LayoutContextValue | null>(null);

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [ragMode, setRagModeState] = useState(false);
  const [qaMode, setQaModeState] = useState<"quick" | "deep">("quick");
  const [fullEvidenceMode, setFullEvidenceModeState] = useState(false);
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [sidebarWidth, setSidebarWidth] = useState(308);
  const [inspectorWidth, setInspectorWidth] = useState(360);

  const refreshSkills = useCallback(async () => {
    setSkills(await listSkills());
  }, []);

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
    Promise.all([getRagMode(), listSkills()])
      .then(([rag, skills]) => {
        setRagModeState(rag.enabled);
        setSkills(skills);
      })
      .catch(() => {
        setRagModeState(false);
        setSkills([]);
      });
  }, []);

  const value: LayoutContextValue = {
    ragMode,
    qaMode,
    fullEvidenceMode,
    skills,
    sidebarWidth,
    inspectorWidth,
    setFullEvidenceMode: setFullEvidenceModeState,
    setQaMode: setQaModeState,
    setSidebarWidth,
    setInspectorWidth,
    toggleRagMode,
    refreshSkills
  };

  return <LayoutContext.Provider value={value}>{children}</LayoutContext.Provider>;
}

export function useLayoutContext() {
  const value = useContext(LayoutContext);
  if (!value) {
    throw new Error("useLayoutContext must be used inside AppProvider");
  }
  return value;
}

export { LayoutContext };
