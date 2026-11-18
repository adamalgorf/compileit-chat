import { describe, expect, it } from "vitest"

import { toChatMessages } from "@/lib/history"
import type { StoredMessage } from "@/lib/types"

const at = "2026-11-18T10:00:00Z"
const source = { title: "Kontakta oss", url: "https://compileit.com/kontakt" }

describe("toChatMessages", () => {
  it("maps saved turns, linking each answer to its question", () => {
    const stored: StoredMessage[] = [
      { role: "user", content: "Fråga 1", sources: [], status: null, created_at: at },
      { role: "assistant", content: "Svar 1", sources: [source], status: "done", created_at: at },
      { role: "user", content: "Fråga 2", sources: [], status: null, created_at: at },
      { role: "assistant", content: "Halv", sources: [], status: "stopped", created_at: at },
    ]

    const messages = toChatMessages("c1", stored)

    expect(messages.map((m) => m.id)).toEqual(["c1-0", "c1-1", "c1-2", "c1-3"])
    expect(messages[1]).toMatchObject({ question: "Fråga 1", sources: [source], status: "done" })
    expect(messages[3]).toMatchObject({ question: "Fråga 2", content: "Halv", status: "stopped" })
  })

  it("shows a saved error as an error (retryable), not as answer text", () => {
    const [, failed] = toChatMessages("c1", [
      { role: "user", content: "Fråga", sources: [], status: null, created_at: at },
      {
        role: "assistant",
        content: "Något gick fel.",
        sources: [],
        status: "error",
        created_at: at,
      },
    ])

    expect(failed).toMatchObject({
      status: "error",
      content: "",
      error: "Något gick fel.",
      question: "Fråga",
    })
  })
})
