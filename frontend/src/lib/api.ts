import type { ChatStreamEvent, ChatStreamEventName } from "@/lib/chatEvents";

export type ToolCall = {
  tool: string;
  input: string;
  output: string;
  meta?: {
    code?: number;
    message?: string;
    trace_id?: string;
    backend?: string;
    warning?: string;
    status?: string;
    final_route?: string;
    reason?: string;
    path?: string;
    query?: string;
    skill?: string;
    count?: number;
    service_trace_ids?: Record<string, string | null>;
    service_backends?: Record<string, string | null>;
  };
};

export type PlannerStep = {
  stage: string;
  label: string;
  detail?: string;
  skill?: string;
};

export type DeepTraceStep = {
  step: number;
  round?: number;
  action_index?: number;
  skill?: string;
  tool?: string;
  status?: string;
  input?: Record<string, unknown>;
  why_this_step?: string;
  new_evidence_count?: number;
  new_evidence?: EvidenceItem[];
  coverage_before_step?: Record<string, unknown>;
  coverage_after_step?: Record<string, unknown>;
};

export type EvidenceBundle = {
  evidence_paths?: string[];
  factual_evidence?: EvidenceItem[];
  case_references?: EvidenceItem[];
  book_citations?: string[];
  coverage?: {
    gaps?: string[];
    factual_count?: number;
    case_count?: number;
    evidence_path_count?: number;
    sufficient?: boolean;
    [key: string]: unknown;
  };
};

export type RetrievalResult = {
  text: string;
  score: number;
  source: string;
};

export type EvidenceItem = {
  evidence_type?: string;
  source_type: string;
  source: string;
  snippet: string;
  score: number | null;
  document?: string;
  fact_id?: string;
  source_book?: string;
  source_chapter?: string;
  source_text?: string;
  confidence?: number | null;
  predicate?: string;
  target?: string;
  path_nodes?: string[];
  path_edges?: string[];
  path_sources?: Array<{
    source_book?: string;
    source_chapter?: string;
    fact_id?: string;
    source_text?: string;
    confidence?: number | null;
  }>;
};

export type RouteEvent = {
  route: string | null;
  reason: string;
  status: string;
  final_route?: string | null;
  executed_routes?: string[];
  degradation?: Array<{
    from: string;
    to: string;
    reason: string;
  }>;
  service_health?: Record<string, unknown>;
  service_trace_ids?: Record<string, string | null>;
  service_backends?: Record<string, string | null>;
};

export type GraphVizNode = {
  id: string;
  label: string;
  type: string;
  type_label?: string;
  score?: number | null;
  evidence_count?: number;
  source_count?: number;
  is_center?: boolean;
  is_schema?: boolean;
};

export type GraphVizEdge = {
  source: string;
  target: string;
  predicate: string;
  evidence_count?: number;
  source_books?: string[];
  source_text?: string;
  confidence?: number | null;
  reverse?: boolean;
  is_schema?: boolean;
};

export type GraphVizPayload = {
  nodes: GraphVizNode[];
  edges: GraphVizEdge[];
  meta: {
    kind?: string;
    center?: string;
    depth: number;
    limit?: number;
    truncated: boolean;
    node_total_before_limit?: number;
    edge_total_before_limit?: number;
    graph_backend?: string;
    graph_node_count?: number;
    graph_edge_count?: number;
    graph_evidence_count?: number;
    note?: string;
  };
};

export type SessionSummary = {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
};

export type SessionHistory = {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  compressed_context?: string;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    tool_calls?: ToolCall[];
    route?: RouteEvent;
    evidence?: EvidenceItem[];
    planner_steps?: PlannerStep[];
    deep_trace?: DeepTraceStep[];
    evidence_bundle?: EvidenceBundle;
    notes?: string[];
    citations?: string[];
    qa_mode?: "quick" | "deep";
  }>;
};

export type SkillMeta = {
  name: string;
  description: string;
  path: string;
  preferred_tools?: string[];
  workflow_steps?: string[];
  output_focus?: string[];
  stop_rules?: string[];
  trigger_phrases?: string[];
  preferred_path_patterns?: string[];
  examples?: string[];
};

export type StreamHandlers = {
  onEvent: (event: ChatStreamEvent) => void;
};

export type StreamChatOptions = {
  signal?: AbortSignal;
};

const JSON_HEADERS = {
  "Content-Type": "application/json"
} as const;

function getApiBase() {
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (configuredBase) {
    return configuredBase.replace(/\/+$/, "");
  }

  return `${window.location.protocol}//${window.location.hostname}:8002/api`;
}

function createJsonRequest(init?: RequestInit): RequestInit {
  return {
    ...init,
    headers: {
      ...JSON_HEADERS,
      ...(init?.headers ?? {})
    }
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, createJsonRequest(init));

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

function parseSseBlock(block: string): ChatStreamEvent | null {
  const lines = block.replace(/\r\n/g, "\n").split("\n");
  let event: ChatStreamEventName = "token";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim() as ChatStreamEventName;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!dataLines.length) {
    return null;
  }

  return {
    event,
    data: parseSseJson(dataLines.join("\n"), event)
  };
}

function parseSseJson(payload: string, event: ChatStreamEventName): Record<string, unknown> {
  try {
    const parsed = JSON.parse(payload) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return { value: parsed };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Malformed SSE ${event} event: ${message}`);
  }
}

export async function listSessions() {
  return request<SessionSummary[]>("/sessions");
}

export async function createSession(title = "新会话") {
  return request<SessionSummary>("/sessions", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export async function renameSession(sessionId: string, title: string) {
  return request<SessionSummary>(`/sessions/${sessionId}`, {
    method: "PUT",
    body: JSON.stringify({ title })
  });
}

export async function deleteSession(sessionId: string) {
  return request<{ ok: boolean }>(`/sessions/${sessionId}`, {
    method: "DELETE"
  });
}

export async function getSessionHistory(sessionId: string) {
  return request<SessionHistory>(`/sessions/${sessionId}/history`);
}

export async function getSessionTokens(sessionId: string) {
  return request<{
    system_tokens: number;
    message_tokens: number;
    total_tokens: number;
  }>(`/tokens/session/${sessionId}`);
}

export async function listSkills() {
  return request<SkillMeta[]>("/skills");
}

export async function loadFile(path: string) {
  return request<{ path: string; content: string }>(
    `/files?path=${encodeURIComponent(path)}`
  );
}

export async function saveFile(path: string, content: string) {
  return request<{ ok: boolean; path: string }>("/files", {
    method: "POST",
    body: JSON.stringify({ path, content })
  });
}

export async function getRagMode() {
  return request<{ enabled: boolean }>("/config/rag-mode");
}

export async function setRagMode(enabled: boolean) {
  return request<{ enabled: boolean }>("/config/rag-mode", {
    method: "PUT",
    body: JSON.stringify({ enabled })
  });
}

export async function getGraphSchemaSummary() {
  return request<GraphVizPayload>("/graph/schema-summary");
}

export async function getGraphSubgraph(entity: string, depth = 2, limit = 120) {
  const query = new URLSearchParams({
    entity,
    depth: String(depth),
    limit: String(limit)
  });
  return request<GraphVizPayload>(`/graph/subgraph?${query.toString()}`);
}

export async function compressSession(sessionId: string) {
  return request<{ archived_count: number; remaining_count: number }>(
    `/sessions/${sessionId}/compress`,
    { method: "POST" }
  );
}

export async function streamChat(
  payload: {
    message: string;
    session_id: string;
    mode: "quick" | "deep";
    top_k?: number;
  },
  handlers: StreamHandlers,
  options: StreamChatOptions = {}
) {
  const response = await fetch(`${getApiBase()}/chat`, createJsonRequest({
    method: "POST",
    signal: options.signal,
    body: JSON.stringify({
      ...payload,
      stream: true
    })
  }));

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flushBlock = (block: string) => {
    const streamEvent = parseSseBlock(block);
    if (!streamEvent) {
      return;
    }
    if (streamEvent.event === "error") {
      throw new Error(String(streamEvent.data.error ?? "Chat stream failed"));
    }
    handlers.onEvent(streamEvent);
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    for (let boundary = buffer.indexOf("\n\n"); boundary >= 0; boundary = buffer.indexOf("\n\n")) {
      flushBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
    }

    if (done) {
      if (buffer.trim()) {
        flushBlock(buffer);
      }
      break;
    }
  }
}
