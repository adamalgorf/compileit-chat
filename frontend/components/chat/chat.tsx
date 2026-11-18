"use client"

import { ArrowDown, PanelLeft, SquarePen } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { useAuth } from "@/components/auth/auth-provider"
import { AssistantMessage } from "@/components/chat/assistant-message"
import { Composer } from "@/components/chat/composer"
import { EmptyState } from "@/components/chat/empty-state"
import { Sidebar } from "@/components/chat/sidebar"
import { UserMessage } from "@/components/chat/user-message"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
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
  const [sheetOpen, setSheetOpen] = useState(false)

  const title =
    history.conversations.find((c) => c.id === chat.conversationId)?.title ?? "Ny konversation"

  const send = (text: string) => {
    chat.send(text)
    scrollToBottom("instant") // a new question always brings the conversation into view
  }

  const sidebarProps = {
    user,
    conversations: history.conversations,
    loaded: history.loaded,
    activeId: chat.conversationId,
    onOpen: (id: string) => {
      chat.openConversation(id)
      setSheetOpen(false)
    },
    onNew: () => {
      chat.newConversation()
      setSheetOpen(false)
    },
    onDelete: (id: string) => {
      void history.remove(id).then(() => toast.success("Konversationen togs bort"))
      if (id === chat.conversationId) chat.newConversation()
    },
    onLogout: () => void logout(),
  }

  return (
    <div className="flex h-dvh bg-background">
      <aside className="hidden w-72 shrink-0 border-r border-sidebar-border md:block">
        <Sidebar {...sidebarProps} />
      </aside>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="left" className="w-80 max-w-[85%] p-0">
          <SheetTitle className="sr-only">Konversationer</SheetTitle>
          <SheetDescription className="sr-only">Dina sparade konversationer</SheetDescription>
          <Sidebar {...sidebarProps} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-3 md:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSheetOpen(true)}
            aria-label="Visa konversationer"
          >
            <PanelLeft aria-hidden />
          </Button>
          <h1 className="min-w-0 flex-1 truncate text-sm font-medium">{title}</h1>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={sidebarProps.onNew}
                aria-label="Ny konversation"
                className="md:hidden"
              >
                <SquarePen aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Ny konversation</TooltipContent>
          </Tooltip>
        </header>

        <main ref={scrollRef} className="relative flex-1 overflow-y-auto overscroll-contain">
          <div ref={contentRef} className="mx-auto flex min-h-full max-w-3xl flex-col px-4 md:px-6">
            {chat.loading && <ConversationSkeleton />}
            {!chat.loading && !chat.messages.length && (
              <EmptyState username={user.username} onPick={send} />
            )}
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

        <footer className="relative shrink-0 bg-gradient-to-t from-background via-background to-background/0 pt-2 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
          {!atBottom && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => scrollToBottom()}
              className="absolute -top-10 left-1/2 -translate-x-1/2 rounded-full bg-background shadow-md"
            >
              <ArrowDown aria-hidden />
              Till senaste
            </Button>
          )}
          <div className="mx-auto max-w-3xl px-4 md:px-6">
            <Composer streaming={chat.streaming} onSend={send} onStop={chat.stop} />
            <p className="mt-2 text-center text-[11px] text-muted-foreground">
              Svaren bygger på compileit.com och kan innehålla fel. Kontrollera gärna källan.
            </p>
          </div>
        </footer>
      </div>

      <StatusAnnouncer messages={chat.messages} />
    </div>
  )
}

function ConversationSkeleton() {
  return (
    <div className="space-y-8 py-8" aria-busy="true" aria-label="Laddar konversationen">
      <Skeleton className="ml-auto h-10 w-2/5 rounded-2xl" />
      <div className="flex gap-3">
        <Skeleton className="size-7 shrink-0 rounded-lg" />
        <div className="flex-1 space-y-2.5">
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/5" />
        </div>
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
