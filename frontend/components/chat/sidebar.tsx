"use client"

import { SquarePen } from "lucide-react"

import { BrandMark, BrandName } from "@/components/brand"
import { ConversationList } from "@/components/chat/conversation-list"
import { UserMenu } from "@/components/chat/user-menu"
import { Button } from "@/components/ui/button"
import type { ConversationSummary, User } from "@/lib/types"

export type SidebarProps = {
  user: User
  conversations: ConversationSummary[]
  loaded: boolean
  activeId: string
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onLogout: () => void
}

/** Brand, "Ny konversation", the saved conversations and the account menu. */
export function Sidebar({ user, onNew, onLogout, ...list }: SidebarProps) {
  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 shrink-0 items-center gap-2.5 px-4">
        <BrandMark />
        <BrandName />
      </div>
      <div className="px-3 pt-1 pb-3">
        <Button
          variant="outline"
          className="h-9 w-full justify-start gap-2 bg-background shadow-xs"
          onClick={onNew}
        >
          <SquarePen aria-hidden />
          Ny konversation
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pb-3">
        <ConversationList {...list} />
      </div>
      <div className="shrink-0 border-t border-sidebar-border p-2">
        <UserMenu user={user} onLogout={onLogout} />
      </div>
    </div>
  )
}
