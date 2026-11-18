import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { AssistantMessage } from "@/components/chat/assistant-message"
import { Composer } from "@/components/chat/composer"
import { EmptyState, SUGGESTIONS } from "@/components/chat/empty-state"
import { TooltipProvider } from "@/components/ui/tooltip"
import type { AssistantMessage as AssistantMessageData } from "@/lib/types"

function message(overrides: Partial<AssistantMessageData>): AssistantMessageData {
  return {
    id: "a1",
    role: "assistant",
    question: "Fråga?",
    content: "",
    status: "done",
    activity: [],
    sources: [],
    ...overrides,
  }
}

function renderAnswer(data: Partial<AssistantMessageData>, onRetry = vi.fn()) {
  render(
    <TooltipProvider>
      <AssistantMessage message={message(data)} onRetry={onRetry} />
    </TooltipProvider>,
  )
  return onRetry
}

describe("AssistantMessage", () => {
  it("shows what the agent is doing while it works", () => {
    renderAnswer({
      status: "streaming",
      activity: [{ tool: "search_website", query: "AI-tjänster" }],
    })

    expect(screen.getByText(/Söker på webbplatsen: "AI-tjänster"/)).toBeInTheDocument()
  })

  it("renders markdown links safely in a new tab and never renders raw HTML", () => {
    renderAnswer({
      content: 'Se [Kontakt](https://compileit.com/kontakt). <img src=x onerror="alert(1)">',
    })

    const link = screen.getByRole("link", { name: "Kontakt" })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
    expect(document.querySelector("img")).toBeNull()
  })

  it("drops javascript: links", () => {
    renderAnswer({ content: "[klicka](javascript:alert(1))" })

    expect(screen.queryByRole("link", { name: "klicka" })?.getAttribute("href") ?? "").not.toMatch(
      /javascript/,
    )
  })

  it("shows source cards with title and domain when done", () => {
    renderAnswer({
      content: "Svar",
      sources: [{ title: "Om Compileit", url: "https://compileit.com/om-oss" }],
    })

    const card = screen.getByRole("link", { name: /Om Compileit/ })
    expect(card).toHaveAttribute("href", "https://compileit.com/om-oss")
    expect(card).toHaveTextContent("compileit.com/om-oss")
  })

  it("offers retry after an error", async () => {
    const onRetry = renderAnswer({ status: "error", error: "Något gick fel." })

    expect(screen.getByRole("alert")).toHaveTextContent("Något gick fel.")
    await userEvent.click(screen.getByRole("button", { name: "Försök igen" }))
    expect(onRetry).toHaveBeenCalledWith("a1")
  })
})

describe("Composer", () => {
  it("sends on Enter, adds a line on Shift+Enter, and clears after sending", async () => {
    const onSend = vi.fn()
    render(<Composer streaming={false} onSend={onSend} onStop={vi.fn()} />)
    const input = screen.getByLabelText("Din fråga")

    await userEvent.type(input, "Rad 1{Shift>}{Enter}{/Shift}Rad 2{Enter}")

    expect(onSend).toHaveBeenCalledWith("Rad 1\nRad 2")
    expect(input).toHaveValue("")
  })

  it("does not send empty questions", async () => {
    const onSend = vi.fn()
    render(<Composer streaming={false} onSend={onSend} onStop={vi.fn()} />)

    await userEvent.type(screen.getByLabelText("Din fråga"), "   {Enter}")

    expect(onSend).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Skicka fråga" })).toBeDisabled()
  })

  it("swaps send for stop while an answer streams", async () => {
    const onStop = vi.fn()
    render(<Composer streaming onSend={vi.fn()} onStop={onStop} />)

    await userEvent.click(screen.getByRole("button", { name: "Stoppa svaret" }))

    expect(onStop).toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "Skicka fråga" })).toBeNull()
  })
})

describe("EmptyState", () => {
  it("asks a suggested question when its chip is clicked", async () => {
    const onPick = vi.fn()
    render(<EmptyState onPick={onPick} />)

    await userEvent.click(screen.getByRole("button", { name: SUGGESTIONS[1] }))

    expect(onPick).toHaveBeenCalledWith(SUGGESTIONS[1])
  })
})
