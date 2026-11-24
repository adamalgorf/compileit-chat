"use client"

import { MoreHorizontal, Trash2 } from "lucide-react"
import { useState } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { ConversationSummary } from "@/lib/types"

type Group = { label: string; conversations: ConversationSummary[] }

const DAY = 24 * 60 * 60 * 1000

/** Buckets like most chat products: Idag, Igår, Senaste 7 dagarna, Äldre (empty ones dropped). */
export function groupByDate(conversations: ConversationSummary[], now = new Date()): Group[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const groups: Group[] = [
    { label: "Idag", conversations: [] },
    { label: "Igår", conversations: [] },
    { label: "Senaste 7 dagarna", conversations: [] },
    { label: "Äldre", conversations: [] },
  ]
  for (const conversation of conversations) {
    const time = new Date(conversation.updatedAt).getTime()
    const index =
      time >= startOfToday
        ? 0
        : time >= startOfToday - DAY
          ? 1
          : time >= startOfToday - 7 * DAY
            ? 2
            : 3
    groups[index]!.conversations.push(conversation)
  }
  return groups.filter((group) => group.conversations.length > 0)
}

/**
 * Saved conversations grouped by date. Each has a menu to delete it, after a confirmation dialog.
 */
export function ConversationList({
  conversations,
  activeId,
  loaded,
  onOpen,
  onDelete,
}: {
  conversations: ConversationSummary[]
  activeId: string
  loaded: boolean
  onOpen: (id: string) => void
  onDelete: (id: string) => void
}) {
  const [pendingDelete, setPendingDelete] = useState<ConversationSummary | null>(null)

  if (!loaded) {
    return (
      <div className="space-y-2 px-3 py-2" aria-busy="true" aria-label="Laddar konversationer">
        {[70, 85, 60].map((width) => (
          <Skeleton key={width} className="h-8" style={{ width: `${width}%` }} />
        ))}
      </div>
    )
  }

  if (!conversations.length) {
    return (
      <p className="mx-3 rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
        Dina konversationer sparas här.
      </p>
    )
  }

  return (
    <>
      <nav aria-label="Konversationer" className="space-y-4 px-2">
        {groupByDate(conversations).map((group) => (
          <section key={group.label}>
            <h3 className="px-2 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
              {group.label}
            </h3>
            <ul className="space-y-px">
              {group.conversations.map((conversation) => {
                const active = conversation.id === activeId
                return (
                  <li key={conversation.id} className="group/item relative">
                    <button
                      type="button"
                      onClick={() => onOpen(conversation.id)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex w-full items-center rounded-md py-1.5 pr-8 pl-2.5 text-left text-sm text-sidebar-foreground/80 transition-colors outline-none hover:bg-sidebar-accent/60 hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                        active &&
                          "bg-sidebar-accent font-medium text-sidebar-accent-foreground before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-brand",
                      )}
                    >
                      <span className="truncate">{conversation.title}</span>
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        aria-label={`Fler val för "${conversation.title}"`}
                        className="absolute top-1/2 right-1 flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity outline-none group-hover/item:opacity-100 hover:bg-sidebar-accent hover:text-foreground focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-sidebar-ring data-[state=open]:opacity-100 max-md:opacity-100"
                      >
                        <MoreHorizontal className="size-4" aria-hidden />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" side="right" className="w-44">
                        <DropdownMenuItem
                          variant="destructive"
                          onSelect={() => setPendingDelete(conversation)}
                        >
                          <Trash2 aria-hidden />
                          Ta bort
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </li>
                )
              })}
            </ul>
          </section>
        ))}
      </nav>

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Ta bort konversationen?</AlertDialogTitle>
            <AlertDialogDescription>
              ”{pendingDelete?.title}” och dess historik tas bort permanent. Det går inte att ångra.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Avbryt</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => pendingDelete && onDelete(pendingDelete.id)}
            >
              Ta bort
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
