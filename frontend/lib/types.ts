/**
 * Wire contract with the backend: mirrors `backend/.../interface/api/sse.py`.
 * One SSE event per variant; a stream ends with either `done` or `error`.
 */
export type ChatStreamEvent =
  | { type: "token"; text: string }
  | { type: "tool_start"; tool: string; query: string | null }
  | { type: "sources"; sources: SourceLink[] }
  | { type: "done" }
  | { type: "error"; message: string }

export type SourceLink = { title: string; url: string }

/** A tool the agent ran while answering, shown as visible activity. */
export type ToolActivity = { tool: string; query: string | null }

export type UserMessage = { id: string; role: "user"; content: string }

export type AssistantStatus = "streaming" | "done" | "error" | "stopped"

export type AssistantMessage = {
  id: string
  role: "assistant"
  /** The question this answers, kept so the answer can be retried. */
  question: string
  content: string
  status: AssistantStatus
  activity: ToolActivity[]
  sources: SourceLink[]
  error?: string
}

export type ChatMessage = UserMessage | AssistantMessage
