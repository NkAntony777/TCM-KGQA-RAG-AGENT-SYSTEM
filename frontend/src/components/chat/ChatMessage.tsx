"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { AnswerTraceTimeline } from "@/components/chat/AnswerTraceTimeline";
import { EvidenceCard } from "@/components/chat/EvidenceCard";
import { GraphEvidenceView } from "@/components/chat/GraphEvidenceView";
import { GraphPathCard } from "@/components/chat/GraphPathCard";
import { RetrievalCard } from "@/components/chat/RetrievalCard";
import { RouteCard } from "@/components/chat/RouteCard";
import { ThoughtChain } from "@/components/chat/ThoughtChain";
import type { DeepTraceStep, EvidenceBundle, EvidenceItem, PlannerStep, RetrievalResult, RouteEvent, SkillMeta, ToolCall } from "@/lib/api";

export function ChatMessage({
  role,
  content,
  toolCalls,
  retrievals,
  route,
  evidence,
  plannerSteps,
  deepTrace,
  evidenceBundle,
  notes,
  citations,
  qaMode,
  skills
}: {
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
  skills: SkillMeta[];
}) {
  const isUser = role === "user";

  return (
    <article
      className={`max-w-[90%] rounded-[28px] px-5 py-4 ${
        isUser
          ? "ml-auto bg-[rgba(13,37,48,0.92)] text-white"
          : "panel mr-auto text-[var(--color-ink)]"
      }`}
    >
      {!isUser && (
        <AnswerTraceTimeline
          deepTrace={deepTrace}
          evidenceBundle={evidenceBundle}
          plannerSteps={plannerSteps}
          qaMode={qaMode}
          route={route}
        />
      )}
      {!isUser && <RetrievalCard results={retrievals} />}
      {!isUser && <RouteCard route={route} />}
      {!isUser && <GraphEvidenceView items={evidence} />}
      {!isUser && <GraphPathCard items={evidence} />}
      {!isUser && <EvidenceCard items={evidence} />}
      {!isUser && (
        <ThoughtChain
          citations={citations}
          deepTrace={deepTrace}
          evidenceBundle={evidenceBundle}
          notes={notes}
          plannerSteps={plannerSteps}
          qaMode={qaMode}
          skills={skills}
          toolCalls={toolCalls}
        />
      )}
      <div className={isUser ? "whitespace-pre-wrap leading-7" : "markdown"}>
        {isUser ? (
          content
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content || "正在思考..."}
          </ReactMarkdown>
        )}
      </div>
    </article>
  );
}
