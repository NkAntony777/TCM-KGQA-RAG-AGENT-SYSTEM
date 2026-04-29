import { useCallback, useEffect, useRef, useState } from "react";

import {
  compressSession,
  createSession,
  deleteSession,
  getSessionHistory,
  getSessionTokens,
  listSessions,
  renameSession,
  streamChat,
  type SessionSummary
} from "@/lib/api";
import { applyChatStreamEvent } from "@/lib/chatEvents";
import { createMessage, type Message, type TokenStats, toUiMessages } from "@/lib/storeModels";

export function useSessionState({ qaMode }: { qaMode: "quick" | "deep" }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokenStats, setTokenStats] = useState<TokenStats | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      streamAbortRef.current?.abort();
    };
  }, []);

  const refreshSessions = useCallback(async () => {
    setSessions(await listSessions());
  }, []);

  const refreshSessionDetails = useCallback(async (sessionId: string) => {
    const [history, tokens] = await Promise.all([
      getSessionHistory(sessionId),
      getSessionTokens(sessionId)
    ]);
    setMessages(toUiMessages(history.messages));
    setTokenStats(tokens);
  }, []);

  const openSession = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    await refreshSessionDetails(sessionId);
  }, [refreshSessionDetails]);

  const clearActiveSession = useCallback(async () => {
    setCurrentSessionId(null);
    setMessages([]);
    setTokenStats(null);
  }, []);

  const createNewSession = useCallback(async () => {
    const created = await createSession();
    await refreshSessions();
    setCurrentSessionId(created.id);
    setMessages([]);
    setTokenStats(null);
  }, [refreshSessions]);

  const selectSession = useCallback(async (sessionId: string) => {
    await openSession(sessionId);
  }, [openSession]);

  const ensureSession = useCallback(async () => {
    if (currentSessionId) {
      return currentSessionId;
    }

    const created = await createSession();
    setCurrentSessionId(created.id);
    await refreshSessions();
    return created.id;
  }, [currentSessionId, refreshSessions]);

  const sendMessage = useCallback(async (value: string) => {
    if (!value.trim() || isStreaming) {
      return;
    }

    const sessionId = await ensureSession();
    const trimmedValue = value.trim();
    const userMessage = createMessage("user", trimmedValue);
    const assistantMessage = createMessage("assistant", "", qaMode);
    let currentAssistantId = assistantMessage.id;
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

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
            // Backend deep mode emits response-boundary markers for persistence/agent phases.
            // The chat UI should keep one visible assistant answer per user question.
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
      }, {
        signal: abortController.signal
      });
    } catch (error) {
      if (abortController.signal.aborted) {
        return;
      }
      const message = error instanceof Error ? error.message : String(error);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === currentAssistantId
            ? { ...item, content: `请求失败：${message}` }
            : item
        )
      );
    } finally {
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
      if (!mountedRef.current) {
        return;
      }
      setIsStreaming(false);
      try {
        await refreshSessions();
        await refreshSessionDetails(sessionId);
      } catch (error) {
        console.error("Failed to refresh session after chat stream", error);
      }
    }
  }, [ensureSession, isStreaming, qaMode, refreshSessionDetails, refreshSessions]);

  const renameCurrentSession = useCallback(async (title: string) => {
    if (!currentSessionId || !title.trim()) {
      return;
    }
    await renameSession(currentSessionId, title.trim());
    await refreshSessions();
  }, [currentSessionId, refreshSessions]);

  const removeSession = useCallback(async (sessionId: string) => {
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
  }, [clearActiveSession, currentSessionId, openSession, refreshSessions]);

  const compressCurrentSession = useCallback(async () => {
    if (!currentSessionId) {
      return;
    }
    await compressSession(currentSessionId);
    await refreshSessionDetails(currentSessionId);
    await refreshSessions();
  }, [currentSessionId, refreshSessionDetails, refreshSessions]);

  const bootstrapSessions = useCallback(async (initialSessions: SessionSummary[]) => {
    setSessions(initialSessions);
    if (initialSessions.length) {
      const initialSessionId = initialSessions[0].id;
      setCurrentSessionId(initialSessionId);
      await refreshSessionDetails(initialSessionId);
      return;
    }

    const created = await createSession();
    setCurrentSessionId(created.id);
    setSessions([created]);
  }, [refreshSessionDetails]);

  return {
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
  };
}
