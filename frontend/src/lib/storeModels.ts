import type {
  EvidenceBundle,
  EvidenceItem,
  DeepTraceStep,
  PlannerStep,
  RetrievalResult,
  RouteEvent,
  SessionSummary,
  SkillMeta,
  ToolCall,
  getSessionHistory
} from "@/lib/api";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
  route?: RouteEvent;
  evidence: EvidenceItem[];
  plannerSteps: PlannerStep[];
  deepTrace: DeepTraceStep[];
  evidenceBundle?: EvidenceBundle;
  notes: string[];
  citations: string[];
  qaMode?: "quick" | "deep";
};

export type TokenStats = {
  system_tokens: number;
  message_tokens: number;
  total_tokens: number;
};

export type AppStore = {
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

export const FIXED_FILES = [
  "workspace/SOUL.md",
  "workspace/IDENTITY.md",
  "workspace/USER.md",
  "workspace/AGENTS.md",
  "memory/MEMORY.md",
  "SKILLS_SNAPSHOT.md"
];

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createMessage(
  role: "user" | "assistant",
  content = "",
  qaMode?: "quick" | "deep"
): Message {
  return {
    id: makeId(),
    role,
    content,
    toolCalls: [],
    retrievals: [],
    evidence: [],
    plannerSteps: [],
    deepTrace: [],
    notes: [],
    citations: [],
    qaMode
  };
}

export function toUiMessages(history: Awaited<ReturnType<typeof getSessionHistory>>["messages"]) {
  const mergedMessages: Message[] = [];

  for (const message of history) {
    const nextMessage: Message = {
      ...createMessage(message.role, message.content ?? "", message.qa_mode),
      toolCalls: message.tool_calls ?? [],
      route: message.route,
      evidence: message.evidence ?? [],
      plannerSteps: message.planner_steps ?? [],
      deepTrace: message.deep_trace ?? [],
      evidenceBundle: message.evidence_bundle,
      notes: message.notes ?? [],
      citations: message.citations ?? []
    };

    const previous = mergedMessages[mergedMessages.length - 1];
    if (previous?.role === "assistant" && nextMessage.role === "assistant") {
      previous.content = [previous.content, nextMessage.content].filter(Boolean).join("\n\n");
      previous.toolCalls = [...previous.toolCalls, ...nextMessage.toolCalls];
      previous.retrievals = [...previous.retrievals, ...nextMessage.retrievals];
      previous.route = nextMessage.route ?? previous.route;
      previous.evidence = [...previous.evidence, ...nextMessage.evidence];
      previous.plannerSteps = [...previous.plannerSteps, ...nextMessage.plannerSteps];
      previous.deepTrace = [...previous.deepTrace, ...nextMessage.deepTrace];
      previous.evidenceBundle = nextMessage.evidenceBundle ?? previous.evidenceBundle;
      previous.notes = [...previous.notes, ...nextMessage.notes];
      previous.citations = [...previous.citations, ...nextMessage.citations];
      previous.qaMode = previous.qaMode === "deep" || nextMessage.qaMode === "deep" ? "deep" : previous.qaMode ?? nextMessage.qaMode;
      continue;
    }

    mergedMessages.push(nextMessage);
  }

  return mergedMessages;
}

export function buildEditableFiles(skills: SkillMeta[]) {
  return [...FIXED_FILES, ...skills.map((skill) => skill.path)];
}
