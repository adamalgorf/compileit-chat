"use client"

import dynamic from "next/dynamic"

/**
 * The app depends on browser-only state (the session cookie check, the active conversation
 * id in localStorage), so it renders on the client only. That avoids a server/client
 * mismatch and lets state initialise synchronously from storage.
 */
export const ChatLoader = dynamic(
  () => import("@/components/app-shell").then((module) => module.App),
  { ssr: false, loading: () => <div className="h-dvh" aria-busy="true" /> },
)
