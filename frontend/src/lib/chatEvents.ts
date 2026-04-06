import type { DeepTraceStep, EvidenceBundle, EvidenceItem, PlannerStep, RouteEvent, ToolCall } from "@/lib/api";

export const CHAT_STREAM_EVENTS = [
  "qa_mode",
  "tool_start",
  "tool_end",
  "route",
  "evidence",
  "planner_step",
  "deep_trace_step",
  "evidence_bundle",
  "notes",
  "citations",
  "token",
  "done",
  "new_response",
  "title",
  "error"
] as const;

export type ChatStreamEventName = (typeof CHAT_STREAM_EVENTS)[number];

export type ChatStreamEvent = {
  event: ChatStreamEventName;
  data: Record<string, unknown>;
};

export type AssistantMessageLike = {
  content: string;
  toolCalls: ToolCall[];
  route?: RouteEvent;
  evidence: EvidenceItem[];
  plannerSteps: PlannerStep[];
  deepTrace: DeepTraceStep[];
  evidenceBundle?: EvidenceBundle;
  notes: string[];
  citations: string[];
  qaMode?: "quick" | "deep";
};

function mergeEvidenceItems(existing: EvidenceItem[], incoming: EvidenceItem[]) {
  const deduped: EvidenceItem[] = [];
  const seen = new Set<string>();
  for (const item of [...existing, ...incoming]) {
    const key = [item.source_type, item.source, item.snippet].join("::");
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(item);
  }
  return deduped;
}

export function applyChatStreamEvent<T extends AssistantMessageLike>(
  message: T,
  streamEvent: ChatStreamEvent
): T {
  const { event, data } = streamEvent;

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
    return {
      ...message,
      evidence: mergeEvidenceItems(message.evidence, nextItems)
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

  if (event === "deep_trace_step") {
    return {
      ...message,
      deepTrace: typeof data.step === "object" && data.step
        ? [...message.deepTrace, data.step as DeepTraceStep]
        : message.deepTrace
    };
  }

  if (event === "evidence_bundle") {
    return {
      ...message,
      evidenceBundle: typeof data.bundle === "object" && data.bundle
        ? (data.bundle as EvidenceBundle)
        : message.evidenceBundle
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
}
