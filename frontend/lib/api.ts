import { readSseEvents, toChatEvent } from "@/lib/sse"
import type { ChatStreamEvent, ConversationSummary, StoredMessage, User } from "@/lib/types"

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "")

export const MESSAGES = {
  unreachable: "Kunde inte nå tjänsten just nu. Kontrollera anslutningen och försök igen.",
  invalid: "Frågan kunde inte skickas. Kontrollera att den inte är tom eller för lång.",
  interrupted: "Svaret avbröts innan det blev klart. Försök igen.",
  loginFailed: "Fel användarnamn eller lösenord.",
} as const

/** A request the backend rejected; `message` is user-facing Swedish. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message)
    this.name = "ApiError"
  }

  get unauthorized(): boolean {
    return this.status === 401
  }
}

/** Every call sends the HttpOnly session cookie set by the login endpoint. */
async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { credentials: "include", ...init })
  } catch (error) {
    if (init.signal?.aborted) throw error
    throw new ApiError(MESSAGES.unreachable)
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
  return response
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await (await request(path, init)).json()) as T
}

const jsonBody = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
})

// --- auth --------------------------------------------------------------------------------

export const login = (username: string, password: string) =>
  json<User>("/api/auth/login", jsonBody({ username, password }))

export const logout = async () => {
  await request("/api/auth/logout", { method: "POST" })
}

/** The logged-in user, or null if there is no valid session. */
export async function currentUser(): Promise<User | null> {
  try {
    return await json<User>("/api/auth/me")
  } catch (error) {
    if (error instanceof ApiError && error.unauthorized) return null
    throw error
  }
}

// --- history -----------------------------------------------------------------------------

export async function listConversations(): Promise<ConversationSummary[]> {
  const rows = await json<{ id: string; title: string; updated_at: string }[]>("/api/conversations")
  return rows.map((row) => ({ id: row.id, title: row.title, updatedAt: row.updated_at }))
}

export const getConversation = (id: string) =>
  json<{ id: string; title: string; messages: StoredMessage[] }>(
    `/api/conversations/${encodeURIComponent(id)}`,
  )

export const deleteConversation = async (id: string) => {
  await request(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" })
}

// --- chat --------------------------------------------------------------------------------

/** Ask a question in a conversation and stream the answer. Aborting `signal` stops it. */
export async function* streamChat(
  conversationId: string,
  message: string,
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await request("/api/chat", {
    ...jsonBody({ conversation_id: conversationId, message }),
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    signal,
  })
  if (!response.body) throw new ApiError(MESSAGES.unreachable)
  for await (const raw of readSseEvents(response.body)) {
    const event = toChatEvent(raw)
    if (event) yield event
  }
}

async function errorMessage(response: Response): Promise<string> {
  if (response.status === 422) return MESSAGES.invalid
  // 401, 404 and 429 carry user-facing Swedish messages from the backend.
  const body: unknown = await response.json().catch(() => null)
  if (typeof body === "object" && body && "detail" in body && typeof body.detail === "string") {
    return body.detail
  }
  return MESSAGES.unreachable
}
