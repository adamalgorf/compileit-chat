"use client"

import { useCallback, useEffect, useReducer, useRef, useState } from "react"

import { ApiError, MESSAGES, getConversation, streamChat } from "@/lib/api"
import { chatReducer, initialChatState, isStreaming } from "@/lib/chat-reducer"
import { toChatMessages } from "@/lib/history"
import { createId } from "@/lib/ids"
import { loadActiveConversation, saveActiveConversation } from "@/lib/storage"
import type { ChatMessage, User } from "@/lib/types"

type Callbacks = {
  /** The session is no longer valid. */
  onUnauthorized: () => void
  /** A turn finished and was saved: e.g. refresh the conversation list. */
  onSaved: () => void
}

export type ChatStream = {
  conversationId: string
  messages: ChatMessage[]
  streaming: boolean
  /** A saved conversation is being loaded. */
  loading: boolean
  send: (text: string) => void
  stop: () => void
  retry: (assistantId: string) => void
  newConversation: () => void
  openConversation: (conversationId: string) => void
}

/**
 * The chat's state machine for one user: the active conversation, its messages and the
 * in-flight request. Conversations are saved by the backend; only the active id is kept in
 * the browser, so a reload reopens it. Transport lives in `lib/api.ts`/`lib/sse.ts`, state
 * transitions in `chat-reducer.ts`.
 */
export function useChatStream(user: User, callbacks: Callbacks): ChatStream {
  const [initial] = useState(() => {
    const stored = loadActiveConversation(user.username)
    return { id: stored ?? createId(), stored: stored !== null }
  })
  const [conversationId, setConversationId] = useState(initial.id)
  const [loading, setLoading] = useState(initial.stored)
  const [state, dispatch] = useReducer(chatReducer, initialChatState)
  const controller = useRef<AbortController | null>(null)
  const loadRequest = useRef(0) // only the latest openConversation() may apply its result
  const latest = useRef(callbacks)
  const streaming = isStreaming(state)

  useEffect(() => {
    latest.current = callbacks
  })

  useEffect(() => {
    saveActiveConversation(user.username, conversationId)
  }, [user.username, conversationId])

  const failed = useCallback((error: unknown) => {
    // 404: the conversation was deleted elsewhere; keep the id and start it afresh.
    if (error instanceof ApiError && error.unauthorized) latest.current.onUnauthorized()
  }, [])

  // Reopen the conversation that was active before a reload.
  useEffect(() => {
    if (!initial.stored) return
    let cancelled = false
    getConversation(initial.id)
      .then(
        (conversation) => {
          if (!cancelled) {
            dispatch({
              type: "loaded",
              messages: toChatMessages(conversation.id, conversation.messages),
            })
          }
        },
        (error: unknown) => {
          if (!cancelled) failed(error)
        },
      )
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [initial, failed])

  // Abort an in-flight answer if the component goes away.
  useEffect(() => () => controller.current?.abort(), [])

  const run = useCallback(
    async (assistantId: string, question: string) => {
      const abort = new AbortController()
      controller.current = abort
      let finished = false
      try {
        for await (const event of streamChat(conversationId, question, abort.signal)) {
          dispatch({ type: "streamed", assistantId, event })
          finished ||= event.type === "done" || event.type === "error"
        }
        if (!finished) dispatch({ type: "failed", assistantId, message: MESSAGES.interrupted })
      } catch (error) {
        if (abort.signal.aborted) {
          dispatch({ type: "stopped", assistantId })
        } else {
          dispatch({
            type: "failed",
            assistantId,
            message: error instanceof ApiError ? error.message : MESSAGES.unreachable,
          })
          failed(error)
        }
      } finally {
        if (controller.current === abort) controller.current = null
        latest.current.onSaved()
      }
    },
    [conversationId, failed],
  )

  const send = useCallback(
    (text: string) => {
      const question = text.trim()
      if (!question || streaming || loading) return
      const assistantId = createId()
      dispatch({ type: "sent", userId: createId(), assistantId, text: question })
      void run(assistantId, question)
    },
    [run, streaming, loading],
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
    loadRequest.current++ // a load still in flight must not overwrite the new conversation
    setConversationId(createId())
    setLoading(false)
    dispatch({ type: "cleared" })
  }, [])

  const openConversation = useCallback(
    (id: string) => {
      controller.current?.abort()
      const request = ++loadRequest.current
      const current = () => request === loadRequest.current
      setConversationId(id)
      setLoading(true)
      dispatch({ type: "cleared" })
      getConversation(id)
        .then(
          (conversation) => {
            if (current()) {
              dispatch({
                type: "loaded",
                messages: toChatMessages(conversation.id, conversation.messages),
              })
            }
          },
          (error: unknown) => {
            if (current()) failed(error)
          },
        )
        .finally(() => {
          if (current()) setLoading(false)
        })
    },
    [failed],
  )

  return {
    conversationId,
    messages: state.messages,
    streaming,
    loading,
    send,
    stop,
    retry,
    newConversation,
    openConversation,
  }
}
