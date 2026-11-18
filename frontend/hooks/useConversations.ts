"use client"

import { useCallback, useEffect, useState } from "react"

import { ApiError, deleteConversation, listConversations } from "@/lib/api"
import type { ConversationSummary } from "@/lib/types"

/** The logged-in user's saved conversations, most recent first. */
export function useConversations(onUnauthorized: () => void) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loaded, setLoaded] = useState(false)

  const handle = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.unauthorized) onUnauthorized()
    },
    [onUnauthorized],
  )

  const refresh = useCallback(() => {
    listConversations().then((list) => {
      setConversations(list)
      setLoaded(true)
    }, handle)
  }, [handle])

  useEffect(() => {
    let cancelled = false
    listConversations().then((list) => {
      if (cancelled) return
      setConversations(list)
      setLoaded(true)
    }, handle)
    return () => {
      cancelled = true
    }
  }, [handle])

  const remove = useCallback(
    async (id: string) => {
      try {
        await deleteConversation(id)
        setConversations((current) => current.filter((c) => c.id !== id))
      } catch (error) {
        handle(error)
      }
    },
    [handle],
  )

  return { conversations, loaded, refresh, remove }
}
