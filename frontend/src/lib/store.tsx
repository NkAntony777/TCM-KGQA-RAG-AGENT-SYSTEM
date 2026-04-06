"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  compressSession,
  createSession,
  deleteSession,
  type EvidenceItem,
  type PlannerStep,
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
  type RouteEvent,
  type RetrievalResult,
  type SessionSummary,
  streamChat,
  type ToolCall
} from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
  route?: RouteEvent;
  evidence: EvidenceItem[];
  plannerSteps: PlannerStep[];
  notes: string[];
  citations: string[];
  qaMode?: "quick" | "deep";
};

type TokenStats = {
  system_tokens: number;
  message_tokens: number;
  total_tokens: number;
};

type AppStore = {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  ragMode: boolean;
  qaMode: "quick" | "deep";
  skills: SkillMeta[];
  editableFiles: string[];
  inspectorPath: string;
  inspectorContent: string;
  inspectorDirty: boolean;
  sidebarWidth: number;
  inspectorWidth: number;
  tokenStats: TokenStats | null;
  createNewSession: () => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (value: string) => Promise<void>;
  toggleRagMode: () => Promise<void>;
  setQaMode: (mode: "quick" | "deep") => void;
  renameCurrentSession: (title: string) => Promise<void>;
  removeSession: (sessionId: string) => Promise<void>;
  loadInspectorFile: (path: string) => Promise<void>;
  updateInspectorContent: (value: string) => void;
  saveInspector: () => Promise<void>;
  compressCurrentSession: () => Promise<void>;
  setSidebarWidth: (width: number) => void;
  setInspectorWidth: (width: number) => void;
};

const FIXED_FILES = [
  "workspace/SOUL.md",
  "workspace/IDENTITY.md",
  "workspace/USER.md",
  "workspace/AGENTS.md",
  "memory/MEMORY.md",
  "SKILLS_SNAPSHOT.md"
];

const StoreContext = createContext<AppStore | null>(null);

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toUiMessages(history: Awaited<ReturnType<typeof getSessionHistory>>["messages"]) {
  return history.map((message) => ({
    id: makeId(),
    role: message.role,
    content: message.content ?? "",
    toolCalls: message.tool_calls ?? [],
    retrievals: [],
    route: message.route,
    evidence: message.evidence ?? [],
    plannerSteps: message.planner_steps ?? [],
    notes: message.notes ?? [],
    citations: message.citations ?? [],
    qaMode: message.qa_mode
  }));
}

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

  const editableFiles = useMemo(
    () => [...FIXED_FILES, ...skills.map((skill) => skill.path)],
    [skills]
  );

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

  async function createNewSession() {
    const created = await createSession();
    await refreshSessions();
    setCurrentSessionId(created.id);
    setMessages([]);
    setTokenStats(null);
  }

  async function selectSession(sessionId: string) {
    setCurrentSessionId(sessionId);
    await refreshSessionDetails(sessionId);
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
    const userMessage: Message = {
      id: makeId(),
      role: "user",
      content: value.trim(),
      toolCalls: [],
      retrievals: [],
      evidence: [],
      plannerSteps: [],
      notes: [],
      citations: []
    };
    const assistantMessage: Message = {
      id: makeId(),
      role: "assistant",
      content: "",
      toolCalls: [],
      retrievals: [],
      evidence: [],
      plannerSteps: [],
      notes: [],
      citations: [],
      qaMode
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    try {
      await streamChat({
        message: value.trim(),
        session_id: sessionId,
        mode: qaMode,
        top_k: 12
      }, {
        onEvent: (event, data) => {
          setMessages((prev) =>
            prev.map((message) => {
              if (message.id !== assistantMessage.id) {
                return message;
              }

              if (event === "qa_mode") {
                return {
                  ...message,
                  qaMode: data.mode === "deep" ? "deep" : "quick"
                };
              }

              if (event === "tool_start") {
                return {
                  ...message,
                  toolCalls: [
                    ...message.toolCalls,
                    {
                      tool: String(data.tool ?? "tool"),
                      input: String(data.input ?? ""),
                      output: ""
                    }
                  ]
                };
              }

              if (event === "tool_end") {
                const meta = typeof data.meta === "object" && data.meta ? (data.meta as ToolCall["meta"]) : undefined;
                const nextToolCalls = [...message.toolCalls];
                if (nextToolCalls.length) {
                  nextToolCalls[nextToolCalls.length - 1] = {
                    ...nextToolCalls[nextToolCalls.length - 1],
                    output: String(data.output ?? ""),
                    meta
                  };
                }
                return {
                  ...message,
                  toolCalls: nextToolCalls
                };
              }

              if (event === "route") {
                return {
                  ...message,
                  route: data as RouteEvent
                };
              }

              if (event === "evidence") {
                const nextItems = Array.isArray(data.items) ? (data.items as EvidenceItem[]) : [];
                const merged = [...message.evidence, ...nextItems];
                const deduped: EvidenceItem[] = [];
                const seen = new Set<string>();
                for (const item of merged) {
                  const key = [item.source_type, item.source, item.snippet].join("::");
                  if (seen.has(key)) {
                    continue;
                  }
                  seen.add(key);
                  deduped.push(item);
                }
                return {
                  ...message,
                  evidence: deduped
                };
              }

              if (event === "planner_step") {
                return {
                  ...message,
                  plannerSteps: typeof data.step === "object" && data.step
                    ? [...message.plannerSteps, data.step as PlannerStep]
                    : message.plannerSteps
                };
              }

              if (event === "notes") {
                return {
                  ...message,
                  notes: Array.isArray(data.items) ? data.items.map((item) => String(item)) : message.notes
                };
              }

              if (event === "citations") {
                return {
                  ...message,
                  citations: Array.isArray(data.items) ? data.items.map((item) => String(item)) : message.citations
                };
              }

              if (event === "token") {
                return {
                  ...message,
                  content: `${message.content}${String(data.content ?? "")}`
                };
              }

              if (event === "done" && !message.content) {
                return {
                  ...message,
                  content: String(data.content ?? "")
                };
              }

              return message;
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
        setCurrentSessionId(nextSessions[0].id);
        await refreshSessionDetails(nextSessions[0].id);
      } else {
        setCurrentSessionId(null);
        setMessages([]);
        setTokenStats(null);
      }
    }
  }

  async function loadInspectorFile(path: string) {
    setInspectorPath(path);
    const file = await loadFile(path);
    setInspectorContent(file.content);
    setInspectorDirty(false);
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
      const [initialSessions, rag, initialSkills] = await Promise.all([
        listSessions(),
        getRagMode(),
        listSkills()
      ]);

      setSessions(initialSessions);
      setRagModeState(rag.enabled);
      setSkills(initialSkills);

      if (initialSessions.length) {
        setCurrentSessionId(initialSessions[0].id);
        await refreshSessionDetails(initialSessions[0].id);
      } else {
        const created = await createSession();
        setCurrentSessionId(created.id);
        setSessions([created]);
      }

      const file = await loadFile("memory/MEMORY.md");
      setInspectorPath(file.path);
      setInspectorContent(file.content);
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
