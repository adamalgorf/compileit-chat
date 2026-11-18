"use client"

import { AuthProvider, useAuth } from "@/components/auth/auth-provider"
import { LoginForm } from "@/components/auth/login-form"
import { Chat } from "@/components/chat/chat"

/** Login screen or chat, depending on the session. */
export function App() {
  return (
    <AuthProvider>
      <Screen />
    </AuthProvider>
  )
}

function Screen() {
  const { state } = useAuth()
  switch (state.status) {
    case "loading":
      return <div className="h-dvh" aria-busy="true" />
    case "anonymous":
      return <LoginForm expired={state.expired} />
    case "authenticated":
      // Keyed by user: logging in as someone else starts from a clean state.
      return <Chat key={state.user.username} user={state.user} />
  }
}
