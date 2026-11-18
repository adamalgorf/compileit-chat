import type { AssistantMessage, ChatMessage, ChatStreamEvent } from "@/lib/types"

/**
 * Every change to the conversation goes through this pure reducer, so the streaming logic in
 * `useChatStream` stays small and the state transitions are unit-testable.
 */
export type ChatState = { messages: ChatMessage[] }

export type ChatAction =
  | { type: "sent"; userId: string; assistantId: string; text: string }
  | { type: "streamed"; assistantId: string; event: ChatStreamEvent }
  | { type: "failed"; assistantId: string; message: string }
  | { type: "stopped"; assistantId: string }
  | { type: "retried"; assistantId: string }
  | { type: "cleared" }

export const initialChatState: ChatState = { messages: [] }

/** State restored from storage. A reload mid-answer cannot resume the stream: show it stopped. */
export function restoredChatState(messages: ChatMessage[]): ChatState {
  return {
    messages: messages.map((m) =>
      m.role === "assistant" && m.status === "streaming" ? { ...m, status: "stopped" } : m,
    ),
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "sent":
      return {
        messages: [
          ...state.messages,
          { id: action.userId, role: "user", content: action.text },
          pendingAnswer(action.assistantId, action.text),
        ],
      }
    case "streamed":
      return updateAssistant(state, action.assistantId, (m) => applyEvent(m, action.event))
    case "failed":
      return updateAssistant(state, action.assistantId, (m) => ({
        ...m,
        status: "error",
        error: action.message,
      }))
    case "stopped":
      return updateAssistant(state, action.assistantId, (m) =>
        m.status === "streaming" ? { ...m, status: "stopped" } : m,
      )
    case "retried":
      return updateAssistant(state, action.assistantId, (m) => pendingAnswer(m.id, m.question))
    case "cleared":
      return initialChatState
  }
}

function applyEvent(message: AssistantMessage, event: ChatStreamEvent): AssistantMessage {
  switch (event.type) {
    case "token":
      return { ...message, content: message.content + event.text }
    case "tool_start":
      return {
        ...message,
        activity: [...message.activity, { tool: event.tool, query: event.query }],
      }
    case "sources":
      return { ...message, sources: event.sources }
    case "done":
      return { ...message, status: "done" }
    case "error":
      return { ...message, status: "error", error: event.message }
  }
}

function pendingAnswer(id: string, question: string): AssistantMessage {
  return {
    id,
    role: "assistant",
    question,
    content: "",
    status: "streaming",
    activity: [],
    sources: [],
  }
}

function updateAssistant(
  state: ChatState,
  id: string,
  update: (message: AssistantMessage) => AssistantMessage,
): ChatState {
  return {
    messages: state.messages.map((m) => (m.id === id && m.role === "assistant" ? update(m) : m)),
  }
}

export function isStreaming(state: ChatState): boolean {
  const last = state.messages.at(-1)
  return last?.role === "assistant" && last.status === "streaming"
}
