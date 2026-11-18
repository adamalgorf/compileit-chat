"use client"

import { useCallback, useEffect, useReducer, useRef, useState } from "react"

import { ApiError, MESSAGES, resetSession, streamChat } from "@/lib/api"
import { chatReducer, isStreaming, restoredChatState } from "@/lib/chat-reducer"
import { createId } from "@/lib/ids"
import {
  clearMessages,
  loadMessages,
  loadSessionId,
  saveMessages,
  saveSessionId,
} from "@/lib/storage"
import type { ChatMessage } from "@/lib/types"

export type ChatStream = {
  messages: ChatMessage[]
  streaming: boolean
  send: (text: string) => void
  stop: () => void
  retry: (assistantId: string) => void
  newConversation: () => void
}

/**
 * The chat's state machine: owns the session id, the transcript and the in-flight request.
 * Transport details live in `lib/api.ts`/`lib/sse.ts`; state transitions in `chat-reducer.ts`.
 *
 * Client-only (see `ChatLoader`): the session is restored synchronously from localStorage on
 * first render, so there is no flash of an empty conversation and no restore effect.
 */
export function useChatStream(): ChatStream {
  const [sessionId, setSessionId] = useState(restoreSessionId)
  const [state, dispatch] = useReducer(chatReducer, sessionId, (id) =>
    restoredChatState(loadMessages(id)),
  )
  const controller = useRef<AbortController | null>(null)
  const streaming = isStreaming(state)

  // Persist the transcript, but not on every streamed token.
  useEffect(() => {
    if (!streaming) saveMessages(sessionId, state.messages)
  }, [sessionId, state.messages, streaming])

  // Abort an in-flight answer if the component goes away.
  useEffect(() => () => controller.current?.abort(), [])

  const run = useCallback(
    async (assistantId: string, question: string) => {
      const abort = new AbortController()
      controller.current = abort
      let finished = false
      try {
        for await (const event of streamChat(sessionId, question, abort.signal)) {
          dispatch({ type: "streamed", assistantId, event })
          finished ||= event.type === "done" || event.type === "error"
        }
        if (!finished) dispatch({ type: "failed", assistantId, message: MESSAGES.interrupted })
      } catch (error) {
        if (abort.signal.aborted) {
          dispatch({ type: "stopped", assistantId })
        } else {
          const message = error instanceof ApiError ? error.message : MESSAGES.unreachable
          dispatch({ type: "failed", assistantId, message })
        }
      } finally {
        if (controller.current === abort) controller.current = null
      }
    },
    [sessionId],
  )

  const send = useCallback(
    (text: string) => {
      const question = text.trim()
      if (!question || streaming) return
      const assistantId = createId()
      dispatch({ type: "sent", userId: createId(), assistantId, text: question })
      void run(assistantId, question)
    },
    [run, streaming],
  )

  const retry = useCallback(
    (assistantId: string) => {
      const message = state.messages.find((m) => m.id === assistantId)
      if (streaming || message?.role !== "assistant") return
      dispatch({ type: "retried", assistantId })
      void run(assistantId, message.question)
    },
    [run, state.messages, streaming],
  )

  const stop = useCallback(() => controller.current?.abort(), [])

  const newConversation = useCallback(() => {
    controller.current?.abort()
    void resetSession(sessionId)
    clearMessages(sessionId)
    const id = createId()
    saveSessionId(id)
    setSessionId(id)
    dispatch({ type: "cleared" })
  }, [sessionId])

  return {
    messages: state.messages,
    streaming,
    send,
    stop,
    retry,
    newConversation,
  }
}

function restoreSessionId(): string {
  const id = loadSessionId() ?? createId()
  saveSessionId(id)
  return id
}
