"use client"

import { ArrowDown, LogOut, Menu, X } from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"

import { useAuth } from "@/components/auth/auth-provider"
import { AssistantMessage } from "@/components/chat/assistant-message"
import { Composer } from "@/components/chat/composer"
import { ConversationList } from "@/components/chat/conversation-list"
import { EmptyState } from "@/components/chat/empty-state"
import { UserMessage } from "@/components/chat/user-message"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useChatStream } from "@/hooks/useChatStream"
import { useConversations } from "@/hooks/useConversations"
import { useStickToBottom } from "@/hooks/useStickToBottom"
import type { ChatMessage, User } from "@/lib/types"

export function Chat({ user }: { user: User }) {
  const { logout, sessionExpired } = useAuth()
  const history = useConversations(sessionExpired)
  const chat = useChatStream(user, { onUnauthorized: sessionExpired, onSaved: history.refresh })
  const { scrollRef, contentRef, atBottom, scrollToBottom } = useStickToBottom()
  const [drawerOpen, setDrawerOpen] = useState(false)

  const send = (text: string) => {
    chat.send(text)
    scrollToBottom("instant") // a new question always brings the conversation into view
  }

  const sidebar = (
    <ConversationList
      conversations={history.conversations}
      activeId={chat.conversationId}
      loaded={history.loaded}
      onOpen={(id) => {
        chat.openConversation(id)
        setDrawerOpen(false)
      }}
      onNew={() => {
        chat.newConversation()
        setDrawerOpen(false)
      }}
      onDelete={(id) => {
        void history.remove(id)
        if (id === chat.conversationId) chat.newConversation()
      }}
    />
  )

  return (
    <div className="flex h-dvh">
      <aside className="hidden w-72 shrink-0 flex-col border-r bg-muted/30 md:flex">
        <div className="flex h-14 shrink-0 items-center border-b px-4">
          <span className="truncate text-sm font-semibold">Compileit-assistenten</span>
        </div>
        {sidebar}
      </aside>
      {drawerOpen && <Drawer onClose={() => setDrawerOpen(false)}>{sidebar}</Drawer>}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="shrink-0 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="mx-auto flex h-14 max-w-3xl items-center justify-between gap-2 px-4">
            <div className="flex min-w-0 items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="-ml-2 md:hidden"
                onClick={() => setDrawerOpen(true)}
                aria-label="Visa konversationer"
              >
                <Menu aria-hidden />
              </Button>
              <div className="min-w-0">
                <h1 className="truncate text-sm font-semibold md:hidden">Compileit-assistenten</h1>
                <p className="truncate text-xs text-muted-foreground">
                  Svarar utifrån compileit.com
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <span className="hidden max-w-40 truncate text-sm text-muted-foreground sm:inline">
                {user.username}
              </span>
              <ThemeToggle />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => void logout()}
                    aria-label="Logga ut"
                  >
                    <LogOut aria-hidden />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Logga ut ({user.username})</TooltipContent>
              </Tooltip>
            </div>
          </div>
        </header>

        <main ref={scrollRef} className="relative flex-1 overflow-y-auto overscroll-contain">
          <div ref={contentRef} className="mx-auto flex min-h-full max-w-3xl flex-col px-4">
            {chat.loading && (
              <p className="py-10 text-sm text-muted-foreground" aria-busy="true">
                Laddar konversationen…
              </p>
            )}
            {!chat.loading && !chat.messages.length && <EmptyState onPick={send} />}
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
      </div>

      <StatusAnnouncer messages={chat.messages} />
    </div>
  )
}

/** The conversation list as an overlay panel on small screens. Escape or a tap outside closes. */
function Drawer({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-40 md:hidden"
      role="dialog"
      aria-modal="true"
      aria-label="Konversationer"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-label="Stäng"
        tabIndex={-1}
      />
      <div className="absolute inset-y-0 left-0 flex w-80 max-w-[85%] flex-col bg-background shadow-xl">
        <div className="flex h-14 shrink-0 items-center justify-between border-b px-4">
          <span className="text-sm font-semibold">Konversationer</span>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Stäng" autoFocus>
            <X aria-hidden />
          </Button>
        </div>
        {children}
      </div>
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
