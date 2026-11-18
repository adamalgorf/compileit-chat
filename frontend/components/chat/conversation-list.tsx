"use client"

import { MessageSquare, SquarePen, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ConversationSummary } from "@/lib/types"

const dateFormat = new Intl.DateTimeFormat("sv-SE", { day: "numeric", month: "short" })
const timeFormat = new Intl.DateTimeFormat("sv-SE", { hour: "2-digit", minute: "2-digit" })

/** "14:05" today, "12 nov." otherwise. */
export function formatUpdated(iso: string, now = new Date()): string {
  const date = new Date(iso)
  return date.toDateString() === now.toDateString()
    ? timeFormat.format(date)
    : dateFormat.format(date)
}

export function ConversationList({
  conversations,
  activeId,
  loaded,
  onOpen,
  onNew,
  onDelete,
}: {
  conversations: ConversationSummary[]
  activeId: string
  loaded: boolean
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}) {
  const remove = (conversation: ConversationSummary) => {
    if (window.confirm(`Ta bort "${conversation.title}"? Det går inte att ångra.`)) {
      onDelete(conversation.id)
    }
  }

  return (
    <nav aria-label="Konversationer" className="flex min-h-0 flex-1 flex-col">
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start" onClick={onNew}>
          <SquarePen aria-hidden />
          Ny konversation
        </Button>
      </div>
      <h2 className="px-4 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Tidigare
      </h2>
      <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {loaded && !conversations.length && (
          <li className="px-2 py-3 text-sm text-muted-foreground">
            Dina konversationer sparas här.
          </li>
        )}
        {conversations.map((conversation) => {
          const active = conversation.id === activeId
          return (
            <li key={conversation.id} className="group relative">
              <button
                type="button"
                onClick={() => onOpen(conversation.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex w-full items-start gap-2 rounded-lg py-2 pr-9 pl-2 text-left text-sm transition-colors outline-none hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50",
                  active && "bg-accent font-medium",
                )}
              >
                <MessageSquare
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2">{conversation.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatUpdated(conversation.updatedAt)}
                  </span>
                </span>
              </button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => remove(conversation)}
                aria-label={`Ta bort konversationen "${conversation.title}"`}
                className="absolute top-1.5 right-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 max-md:opacity-100"
              >
                <Trash2 aria-hidden />
              </Button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
