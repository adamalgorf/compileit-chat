import { describe, expect, it } from "vitest"

import {
  chatReducer,
  initialChatState,
  isStreaming,
  type ChatAction,
  type ChatState,
} from "@/lib/chat-reducer"
import type { AssistantMessage, ChatStreamEvent } from "@/lib/types"

const sent: ChatAction = { type: "sent", userId: "u1", assistantId: "a1", text: "Fråga?" }

function apply(...actions: ChatAction[]): ChatState {
  return actions.reduce(chatReducer, initialChatState)
}

function streamed(event: ChatStreamEvent): ChatAction {
  return { type: "streamed", assistantId: "a1", event }
}

function answer(state: ChatState): AssistantMessage {
  const message = state.messages.find((m) => m.id === "a1")
  if (message?.role !== "assistant") throw new Error("no answer")
  return message
}

describe("chatReducer", () => {
  it("adds the question and a streaming answer placeholder", () => {
    const state = apply(sent)

    expect(state.messages).toEqual([
      { id: "u1", role: "user", content: "Fråga?" },
      {
        id: "a1",
        role: "assistant",
        question: "Fråga?",
        content: "",
        status: "streaming",
        activity: [],
        sources: [],
      },
    ])
    expect(isStreaming(state)).toBe(true)
  })

  it("builds the answer from streamed events", () => {
    const state = apply(
      sent,
      streamed({ type: "tool_start", tool: "search_website", query: "kontakt" }),
      streamed({ type: "token", text: "Mejla " }),
      streamed({ type: "token", text: "oss." }),
      streamed({ type: "sources", sources: [{ title: "Kontakt", url: "https://x/kontakt" }] }),
      streamed({ type: "done" }),
    )

    expect(answer(state)).toMatchObject({
      content: "Mejla oss.",
      status: "done",
      activity: [{ tool: "search_website", query: "kontakt" }],
      sources: [{ title: "Kontakt", url: "https://x/kontakt" }],
    })
    expect(isStreaming(state)).toBe(false)
  })

  it("records server-side and client-side failures", () => {
    expect(answer(apply(sent, streamed({ type: "error", message: "Fel" })))).toMatchObject({
      status: "error",
      error: "Fel",
    })
    expect(
      answer(apply(sent, { type: "failed", assistantId: "a1", message: "Nät" })),
    ).toMatchObject({ status: "error", error: "Nät" })
  })

  it("marks only an unfinished answer as stopped", () => {
    expect(answer(apply(sent, { type: "stopped", assistantId: "a1" })).status).toBe("stopped")
    expect(
      answer(apply(sent, streamed({ type: "done" }), { type: "stopped", assistantId: "a1" }))
        .status,
    ).toBe("done")
  })

  it("retrying resets the answer but keeps its question", () => {
    const state = apply(
      sent,
      streamed({ type: "token", text: "Halv" }),
      { type: "failed", assistantId: "a1", message: "Fel" },
      { type: "retried", assistantId: "a1" },
    )

    expect(answer(state)).toMatchObject({ content: "", status: "streaming", question: "Fråga?" })
    expect(state.messages).toHaveLength(2)
  })

  it("clears the conversation", () => {
    expect(apply(sent, { type: "cleared" })).toEqual(initialChatState)
  })
})

describe("loaded", () => {
  it("replaces the conversation with a saved one", () => {
    const saved = apply(sent, streamed({ type: "done" })).messages

    expect(apply(sent, { type: "loaded", messages: saved }).messages).toEqual(saved)
  })
})
