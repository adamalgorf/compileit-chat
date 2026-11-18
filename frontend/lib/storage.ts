import type { ChatMessage } from "@/lib/types"

/**
 * The session id and the visible transcript live in localStorage, so a reload keeps the
 * conversation. The server holds the agent's memory for the same session id; this is only
 * what the user sees. Storage can be unavailable (private mode, blocked), so every access
 * is guarded and the app works without it.
 */
const SESSION_KEY = "compileit-chat:session-id"
const messagesKey = (sessionId: string) => `compileit-chat:messages:${sessionId}`

export function loadSessionId(): string | null {
  return read(SESSION_KEY)
}

export function saveSessionId(sessionId: string): void {
  write(SESSION_KEY, sessionId)
}

export function loadMessages(sessionId: string): ChatMessage[] {
  const raw = read(messagesKey(sessionId))
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as ChatMessage[]) : []
  } catch {
    return []
  }
}

export function saveMessages(sessionId: string, messages: ChatMessage[]): void {
  write(messagesKey(sessionId), JSON.stringify(messages))
}

export function clearMessages(sessionId: string): void {
  try {
    localStorage.removeItem(messagesKey(sessionId))
  } catch {
    // ignore: storage unavailable
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore: storage unavailable or full; the chat still works for this page view
  }
}
