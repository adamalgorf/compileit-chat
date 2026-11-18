"use client"

import dynamic from "next/dynamic"

/**
 * The conversation lives in the browser (session id and transcript in localStorage), so the
 * chat renders on the client only. That avoids a server/client mismatch and lets the state
 * initialise synchronously from storage.
 */
export const ChatLoader = dynamic(
  () => import("@/components/chat/chat").then((module) => module.Chat),
  { ssr: false, loading: () => <div className="h-dvh" aria-busy="true" /> },
)
