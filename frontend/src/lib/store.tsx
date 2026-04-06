"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  compressSession,
  createSession,
  deleteSession,
  type SkillMeta,
  getRagMode,
  getSessionHistory,
  getSessionTokens,
  listSessions,
  listSkills,
  loadFile,
  renameSession,
  saveFile,
  setRagMode,
  type SessionSummary,
  streamChat
} from "@/lib/api";
import { applyChatStreamEvent } from "@/lib/chatEvents";
import { loadInitialAppState } from "@/lib/storeBootstrap";
import {
  buildEditableFiles,
  createMessage,
  type AppStore,
  type Message,
  type TokenStats,
  toUiMessages
} from "@/lib/storeModels";

const StoreContext = createContext<AppStore | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [ragMode, setRagModeState] = useState(false);
  const [qaMode, setQaModeState] = useState<"quick" | "deep">("quick");
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [inspectorPath, setInspectorPath] = useState("memory/MEMORY.md");
  const [inspectorContent, setInspectorContent] = useState("");
  const [inspectorDirty, setInspectorDirty] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(308);
  const [inspectorWidth, setInspectorWidth] = useState(360);
  const [tokenStats, setTokenStats] = useState<TokenStats | null>(null);

  const editableFiles = useMemo(() => buildEditableFiles(skills), [skills]);

  function applyInspectorFile(file: { path: string; content: string }) {
    setInspectorPath(file.path);
    setInspectorContent(file.content);
    setInspectorDirty(false);
  }

  async function refreshSessions() {
    setSessions(await listSessions());
  }

  async function refreshSkills() {
    setSkills(await listSkills());
  }

  async function refreshSessionDetails(sessionId: string) {
    const [history, tokens] = await Promise.all([
      getSessionHistory(sessionId),
      getSessionTokens(sessionId)
    ]);
    setMessages(toUiMessages(history.messages));
    setTokenStats(tokens);
  }

  async function openSession(sessionId: string) {
    setCurrentSessionId(sessionId);
    await refreshSessionDetails(sessionId);
  }

  async function clearActiveSession() {
    setCurrentSessionId(null);
    setMessages([]);
    setTokenStats(null);
  }

  async function createNewSession() {
    const created = await createSession();
    await refreshSessions();
    setCurrentSessionId(created.id);
    setMessages([]);
    setTokenStats(null);
  }

  async function selectSession(sessionId: string) {
    await openSession(sessionId);
  }

  async function ensureSession() {
    if (currentSessionId) {
      return currentSessionId;
    }

    const created = await createSession();
    setCurrentSessionId(created.id);
    await refreshSessions();
    return created.id;
  }

  async function sendMessage(value: string) {
    if (!value.trim() || isStreaming) {
      return;
    }

    const sessionId = await ensureSession();
    const trimmedValue = value.trim();
    const userMessage = createMessage("user", trimmedValue);
    const assistantMessage = createMessage("assistant", "", qaMode);
    let currentAssistantId = assistantMessage.id;

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    try {
      await streamChat({
        message: trimmedValue,
        session_id: sessionId,
        mode: qaMode,
        top_k: 12
      }, {
        onEvent: (streamEvent) => {
          if (streamEvent.event === "new_response") {
            const nextAssistantMessage = createMessage("assistant", "", qaMode);
            currentAssistantId = nextAssistantMessage.id;
            setMessages((prev) => [...prev, nextAssistantMessage]);
            return;
          }
          setMessages((prev) =>
            prev.map((message) => {
              if (message.id !== currentAssistantId) {
                return message;
              }
              return applyChatStreamEvent(message, streamEvent);
            })
          );
        }
      });
    } finally {
      setIsStreaming(false);
      await refreshSessions();
      await refreshSessionDetails(sessionId);
    }
  }

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

  async function renameCurrentSession(title: string) {
    if (!currentSessionId || !title.trim()) {
      return;
    }
    await renameSession(currentSessionId, title.trim());
    await refreshSessions();
  }

  async function removeSession(sessionId: string) {
    await deleteSession(sessionId);
    await refreshSessions();
    if (currentSessionId === sessionId) {
      const nextSessions = await listSessions();
      setSessions(nextSessions);
      if (nextSessions.length) {
        await openSession(nextSessions[0].id);
      } else {
        await clearActiveSession();
      }
    }
  }

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

  async function compressCurrentSession() {
    if (!currentSessionId) {
      return;
    }
    await compressSession(currentSessionId);
    await refreshSessionDetails(currentSessionId);
    await refreshSessions();
  }

  useEffect(() => {
    void (async () => {
      const initialState = await loadInitialAppState();
      setSessions(initialState.sessions);
      setRagModeState(initialState.ragMode);
      setSkills(initialState.skills);

      if (initialState.sessions.length) {
        const initialSessionId = initialState.sessions[0].id;
        setCurrentSessionId(initialSessionId);
        await refreshSessionDetails(initialSessionId);
      } else {
        const created = await createSession();
        setCurrentSessionId(created.id);
        setSessions([created]);
      }
      applyInspectorFile(initialState.inspectorFile);
    })();
  }, []);

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
