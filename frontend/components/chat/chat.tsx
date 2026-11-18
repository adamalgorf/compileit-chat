"use client"

import { ArrowDown, SquarePen } from "lucide-react"

import { AssistantMessage } from "@/components/chat/assistant-message"
import { Composer } from "@/components/chat/composer"
import { EmptyState } from "@/components/chat/empty-state"
import { UserMessage } from "@/components/chat/user-message"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { useChatStream } from "@/hooks/useChatStream"
import { useStickToBottom } from "@/hooks/useStickToBottom"
import type { ChatMessage } from "@/lib/types"

export function Chat() {
  const chat = useChatStream()
  const { scrollRef, contentRef, atBottom, scrollToBottom } = useStickToBottom()

  const send = (text: string) => {
    chat.send(text)
    scrollToBottom("instant") // a new question always brings the conversation into view
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="shrink-0 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between gap-3 px-4">
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold">Compileit-assistenten</h1>
            <p className="truncate text-xs text-muted-foreground">Svarar utifrån compileit.com</p>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={chat.newConversation}
              disabled={!chat.messages.length}
            >
              <SquarePen aria-hidden />
              Ny konversation
            </Button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main ref={scrollRef} className="relative flex-1 overflow-y-auto overscroll-contain">
        <div ref={contentRef} className="mx-auto flex min-h-full max-w-3xl flex-col px-4">
          {!chat.messages.length && <EmptyState onPick={send} />}
          {chat.messages.length > 0 && (
            <div
              role="log"
              aria-label="Konversation"
              aria-busy={chat.streaming}
              className="space-y-8 py-8"
            >
              {chat.messages.map((message) => (
                <Message key={message.id} message={message} onRetry={chat.retry} />
              ))}
            </div>
          )}
        </div>
      </main>

      <footer className="relative shrink-0 bg-background pb-[max(env(safe-area-inset-bottom),0.75rem)]">
        {!atBottom && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => scrollToBottom()}
            className="absolute -top-12 left-1/2 -translate-x-1/2 rounded-full shadow-sm"
          >
            <ArrowDown aria-hidden />
            Till senaste
          </Button>
        )}
        <div className="mx-auto max-w-3xl px-4">
          <Composer streaming={chat.streaming} onSend={send} onStop={chat.stop} />
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Svaren bygger på compileit.com och kan innehålla fel. Kontrollera gärna källan.
          </p>
        </div>
      </footer>

      <StatusAnnouncer messages={chat.messages} />
    </div>
  )
}

function Message({ message, onRetry }: { message: ChatMessage; onRetry: (id: string) => void }) {
  return message.role === "user" ? (
    <UserMessage content={message.content} />
  ) : (
    <AssistantMessage message={message} onRetry={onRetry} />
  )
}

/**
 * Screen readers get one short announcement per state change instead of every streamed
 * token: "Svarar…", then "Svaret är klart" (or the error).
 */
function StatusAnnouncer({ messages }: { messages: ChatMessage[] }) {
  const last = messages.at(-1)
  let status = ""
  if (last?.role === "assistant") {
    status = {
      streaming: "Svarar…",
      done: "Svaret är klart.",
      error: last.error ?? "",
      stopped: "Svaret stoppades.",
    }[last.status]
  }
  return (
    <div className="sr-only" role="status" aria-live="polite">
      {status}
    </div>
  )
}
