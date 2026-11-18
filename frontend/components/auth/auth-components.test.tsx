import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { App } from "@/components/app-shell"
import { ConversationList, groupByDate } from "@/components/chat/conversation-list"
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

    await userEvent.click(await screen.findByRole("button", { name: "Kontomeny för anna" }))
    expect(await screen.findByRole("menuitem", { name: "Logga ut" })).toBeInTheDocument()
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

  it("marks the active conversation and opens or deletes after confirming", async () => {
    const onOpen = vi.fn()
    const onDelete = vi.fn()
    render(
      <ConversationList
        conversations={conversations}
        activeId="c1"
        loaded
        onOpen={onOpen}
        onDelete={onDelete}
      />,
    )

    expect(screen.getByRole("button", { name: /^Vilka branscher/ })).toHaveAttribute(
      "aria-current",
      "page",
    )
    await userEvent.click(screen.getByRole("button", { name: /^Hur kontaktar/ }))
    expect(onOpen).toHaveBeenCalledWith("c2")

    await userEvent.click(
      screen.getByRole("button", { name: 'Fler val för "Hur kontaktar man er?"' }),
    )
    await userEvent.click(await screen.findByRole("menuitem", { name: "Ta bort" }))
    const dialog = await screen.findByRole("alertdialog")
    expect(dialog).toHaveTextContent("Ta bort konversationen?")
    expect(onDelete).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole("button", { name: "Ta bort" }))

    expect(onDelete).toHaveBeenCalledWith("c2")
  })

  it("groups conversations by how recently they were updated", () => {
    const now = new Date("2026-11-18T15:00:00")
    const at = (iso: string, id: string) => ({
      id,
      title: id,
      updatedAt: new Date(iso).toISOString(),
    })
    const groups = groupByDate(
      [
        at("2026-11-18T09:00:00", "idag"),
        at("2026-11-17T22:00:00", "igar"),
        at("2026-11-14T10:00:00", "veckan"),
        at("2026-10-01T10:00:00", "gammal"),
      ],
      now,
    )
    expect(groups.map((g) => [g.label, g.conversations.map((c) => c.id)])).toEqual([
      ["Idag", ["idag"]],
      ["Igår", ["igar"]],
      ["Senaste 7 dagarna", ["veckan"]],
      ["Äldre", ["gammal"]],
    ])
  })
})
