"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import * as api from "@/lib/api"
import type { User } from "@/lib/types"

type AuthState =
  | { status: "loading" }
  | { status: "anonymous"; expired?: boolean }
  | { status: "authenticated"; user: User }

type Auth = {
  state: AuthState
  /** Throws `ApiError` with a user-facing message on failure. */
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** The server rejected the session (expired or revoked): back to the login screen. */
  sessionExpired: () => void
}

const AuthContext = createContext<Auth | null>(null)

/** Who is logged in. The session itself is an HttpOnly cookie the page cannot read. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" })

  useEffect(() => {
    let cancelled = false
    api.currentUser().then(
      (user) => {
        if (!cancelled) setState(user ? { status: "authenticated", user } : { status: "anonymous" })
      },
      () => {
        if (!cancelled) setState({ status: "anonymous" })
      },
    )
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const user = await api.login(username, password)
    setState({ status: "authenticated", user })
  }, [])

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined) // the cookie is cleared server-side if reachable
    setState({ status: "anonymous" })
  }, [])

  const sessionExpired = useCallback(() => setState({ status: "anonymous", expired: true }), [])

  const value = useMemo(
    () => ({ state, login, logout, sessionExpired }),
    [state, login, logout, sessionExpired],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error("useAuth must be used inside <AuthProvider>")
  return auth
}
