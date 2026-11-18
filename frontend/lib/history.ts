import type { ChatMessage, StoredMessage } from "@/lib/types"

/** Turn messages saved by the backend into the chat's view model. Pure, so it is tested. */
export function toChatMessages(conversationId: string, stored: StoredMessage[]): ChatMessage[] {
  let question = ""
  return stored.map((message, index): ChatMessage => {
    const id = `${conversationId}-${index}`
    if (message.role === "user") {
      question = message.content
      return { id, role: "user", content: message.content }
    }
    const failed = message.status === "error"
    return {
      id,
      role: "assistant",
      question, // the preceding question, so a failed answer can be retried
      content: failed ? "" : message.content,
      status: message.status ?? "done",
      activity: [],
      sources: message.sources,
      error: failed ? message.content : undefined,
    }
  })
}
