import { z } from "zod";

export const SseEventSchema = z.object({
  event: z.string(),
  data: z.unknown(),
});

export const RouteEventSchema = z.object({
  type: z.literal("route"),
  route: z.string().optional(),
  mode: z.string().optional(),
});

export const PlannerStepSchema = z.object({
  type: z.literal("planner_step"),
  step: z.object({
    stage: z.string(),
    label: z.string(),
    detail: z.string().optional(),
  }),
});

export const TokenEventSchema = z.object({
  type: z.literal("token"),
  content: z.string(),
});

export const DoneEventSchema = z.object({
  type: z.literal("done"),
  content: z.string(),
});

export const ErrorEventSchema = z.object({
  type: z.literal("error"),
  error: z.string(),
});

export const ChatResponseSchema = z.object({
  session_id: z.string(),
  title: z.string().optional(),
});
