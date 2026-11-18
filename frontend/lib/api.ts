import { readSseEvents, toChatEvent } from "@/lib/sse"
import type { ChatStreamEvent } from "@/lib/types"

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "")

export const MESSAGES = {
  unreachable: "Kunde inte nå tjänsten just nu. Kontrollera anslutningen och försök igen.",
  invalid: "Frågan kunde inte skickas. Kontrollera att den inte är tom eller för lång.",
  interrupted: "Svaret avbröts innan det blev klart. Försök igen.",
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
}

/** Ask a question and stream the answer's events. Aborting `signal` stops generation. */
export async function* streamChat(
  sessionId: string,
  message: string,
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  for await (const raw of readSseEvents(response.body)) {
    const event = toChatEvent(raw)
    if (event) yield event
  }
}

/** Forget a conversation on the server. Best effort: the client starts afresh regardless. */
export async function resetSession(sessionId: string): Promise<void> {
  try {
    await fetch(`${API_URL}/api/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" })
  } catch {
    // Offline or server down: the old session is simply left to expire.
  }
}

async function errorMessage(response: Response): Promise<string> {
  if (response.status === 422) return MESSAGES.invalid
  if (response.status === 429) {
    // The backend's rate-limit message is already user-facing Swedish.
    const body: unknown = await response.json().catch(() => null)
    if (typeof body === "object" && body && "detail" in body && typeof body.detail === "string") {
      return body.detail
    }
  }
  return MESSAGES.unreachable
}
