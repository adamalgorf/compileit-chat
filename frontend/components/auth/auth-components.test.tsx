import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { App } from "@/components/app-shell"
import { ConversationList, formatUpdated } from "@/components/chat/conversation-list"
import { TooltipProvider } from "@/components/ui/tooltip"

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

describe("login", () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => vi.stubGlobal("fetch", fetchMock))
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it("shows the login form without a session and the error for wrong credentials", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith("/api/auth/me")
        ? json({ detail: "Du behöver logga in." }, 401)
        : json({ detail: "Fel användarnamn eller lösenord." }, 401),
    )
    render(
      <TooltipProvider>
        <App />
      </TooltipProvider>,
    )

    await userEvent.type(await screen.findByLabelText("Användarnamn"), "anna")
    await userEvent.type(screen.getByLabelText("Lösenord"), "fel-losenord")
    await userEvent.click(screen.getByRole("button", { name: "Logga in" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Fel användarnamn eller lösenord.")
    expect(screen.getByLabelText("Lösenord")).toHaveValue("") // cleared after a failure
    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/login"))!
    expect(init?.credentials).toBe("include")
  })

  it("goes straight to the chat with a valid session", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith("/api/auth/me") ? json({ username: "anna" }) : json([]),
    )
    render(
      <TooltipProvider>
        <App />
      </TooltipProvider>,
    )

    expect(await screen.findByRole("button", { name: "Logga ut" })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByText("Dina konversationer sparas här.")).toBeInTheDocument(),
    )
  })
})

describe("ConversationList", () => {
  const conversations = [
    { id: "c1", title: "Vilka branscher jobbar ni med?", updatedAt: "2026-11-18T10:00:00Z" },
    { id: "c2", title: "Hur kontaktar man er?", updatedAt: "2026-11-17T09:00:00Z" },
  ]

  it("marks the active conversation and opens or deletes on request", async () => {
    const onOpen = vi.fn()
    const onDelete = vi.fn()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(
      <ConversationList
        conversations={conversations}
        activeId="c1"
        loaded
        onOpen={onOpen}
        onNew={vi.fn()}
        onDelete={onDelete}
      />,
    )

    expect(screen.getByRole("button", { name: /^Vilka branscher/ })).toHaveAttribute(
      "aria-current",
      "page",
    )
    await userEvent.click(screen.getByRole("button", { name: /^Hur kontaktar/ }))
    await userEvent.click(
      screen.getByRole("button", { name: 'Ta bort konversationen "Hur kontaktar man er?"' }),
    )

    expect(onOpen).toHaveBeenCalledWith("c2")
    expect(onDelete).toHaveBeenCalledWith("c2")
  })

  it("formats today as a time and older days as a date", () => {
    const now = new Date("2026-11-18T15:00:00")
    expect(formatUpdated(new Date("2026-11-18T14:05:00").toISOString(), now)).toBe("14:05")
    expect(formatUpdated(new Date("2026-11-12T09:00:00").toISOString(), now)).toMatch(/12 nov/)
  })
})
