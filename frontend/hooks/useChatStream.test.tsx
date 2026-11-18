import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useChatStream } from "@/hooks/useChatStream"
import { MESSAGES } from "@/lib/api"

function sseResponse(body: string, init: ResponseInit = {}): Response {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
    ...init,
  })
}

const ANSWER = [
  'event: tool_start\ndata: {"tool": "search_website", "query": "kontakt"}\n\n',
  'event: token\ndata: {"text": "Mejla oss."}\n\n',
  'event: sources\ndata: {"sources": [{"title": "Kontakt", "url": "https://x/kontakt"}]}\n\n',
  "event: done\ndata: {}\n\n",
].join("")

describe("useChatStream", () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal("fetch", fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it("streams an answer and persists the conversation for reloads", async () => {
    fetchMock.mockResolvedValue(sseResponse(ANSWER))
    const { result } = renderHook(() => useChatStream())

    act(() => result.current.send("  Hur kontaktar man er?  "))

    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1]).toMatchObject({
      content: "Mejla oss.",
      status: "done",
      sources: [{ title: "Kontakt", url: "https://x/kontakt" }],
    })
    const [, init] = fetchMock.mock.calls[0]!
    expect(JSON.parse(String(init?.body))).toMatchObject({ message: "Hur kontaktar man er?" })

    const reloaded = renderHook(() => useChatStream())
    expect(reloaded.result.current.messages).toEqual(result.current.messages)
  })

  it("shows the backend's message when rate limited", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "För många frågor." }), { status: 429 }),
    )
    const { result } = renderHook(() => useChatStream())

    act(() => result.current.send("Hej"))

    await waitFor(() =>
      expect(result.current.messages[1]).toMatchObject({
        status: "error",
        error: "För många frågor.",
      }),
    )
  })

  it("treats a stream that ends without done/error as interrupted", async () => {
    fetchMock.mockResolvedValue(sseResponse('event: token\ndata: {"text": "Halv"}\n\n'))
    const { result } = renderHook(() => useChatStream())

    act(() => result.current.send("Hej"))

    await waitFor(() =>
      expect(result.current.messages[1]).toMatchObject({
        status: "error",
        error: MESSAGES.interrupted,
      }),
    )
  })

  it("stop aborts the request and marks the answer stopped", async () => {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) =>
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          ),
        ),
    )
    const { result } = renderHook(() => useChatStream())

    act(() => result.current.send("Hej"))
    act(() => result.current.stop())

    await waitFor(() => expect(result.current.messages[1]).toMatchObject({ status: "stopped" }))
  })

  it("a new conversation resets the server session and starts a new id", async () => {
    fetchMock.mockResolvedValue(sseResponse(ANSWER))
    const { result } = renderHook(() => useChatStream())
    act(() => result.current.send("Hej"))
    await waitFor(() => expect(result.current.streaming).toBe(false))
    const [, firstInit] = fetchMock.mock.calls[0]!
    const oldSession = JSON.parse(String(firstInit?.body)).session_id as string

    act(() => result.current.newConversation())

    expect(result.current.messages).toEqual([])
    const [resetUrl, resetInit] = fetchMock.mock.calls[1]!
    expect(String(resetUrl)).toContain(`/api/sessions/${oldSession}`)
    expect(resetInit?.method).toBe("DELETE")
    expect(localStorage.getItem("compileit-chat:session-id")).not.toBe(oldSession)
  })
})
