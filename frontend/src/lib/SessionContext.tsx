"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";

import { listSessions, type SessionSummary } from "@/lib/api";
import { type Message, type TokenStats } from "@/lib/storeModels";
import { useSessionState } from "@/lib/useSessionState";
import { useLayoutContext } from "@/lib/LayoutContext";

type SessionContextValue = {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  tokenStats: TokenStats | null;
  createNewSession: () => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (value: string) => Promise<void>;
  renameCurrentSession: (title: string) => Promise<void>;
  removeSession: (sessionId: string) => Promise<void>;
  compressCurrentSession: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const { qaMode, fullEvidenceMode } = useLayoutContext();

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
  } = useSessionState({ qaMode, fullEvidenceMode });

  useEffect(() => {
    listSessions()
      .then((initialSessions) => bootstrapSessions(initialSessions))
      .catch((error) => console.error("Failed to bootstrap sessions", error));
  }, [bootstrapSessions]);

  const value: SessionContextValue = {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    tokenStats,
    createNewSession,
    selectSession,
    sendMessage,
    renameCurrentSession,
    removeSession,
    compressCurrentSession
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSessionContext() {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSessionContext must be used inside AppProvider");
  }
  return value;
}

export { SessionContext };
