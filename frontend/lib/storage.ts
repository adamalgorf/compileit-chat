/**
 * Only the *active* conversation id lives in the browser, so a reload reopens it. The
 * conversations themselves are saved on the server, per user. Storage can be unavailable
 * (private mode, blocked), so every access is guarded and the app works without it.
 */
const activeKey = (username: string) => `compileit-chat:active-conversation:${username}`

export function loadActiveConversation(username: string): string | null {
  try {
    return localStorage.getItem(activeKey(username))
  } catch {
    return null
  }
}

export function saveActiveConversation(username: string, conversationId: string): void {
  try {
    localStorage.setItem(activeKey(username), conversationId)
  } catch {
    // ignore: storage unavailable
  }
}
