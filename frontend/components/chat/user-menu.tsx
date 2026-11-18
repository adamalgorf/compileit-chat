"use client"

import { Check, ChevronsUpDown, LogOut, Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { User } from "@/lib/types"

const THEMES = [
  { value: "light", label: "Ljust", icon: Sun },
  { value: "dark", label: "Mörkt", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const

/** The account card at the bottom of the sidebar: theme and logout live here. */
export function UserMenu({ user, onLogout }: { user: User; onLogout: () => void }) {
  const { theme, setTheme } = useTheme()
  const initials = user.username.slice(0, 2).toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Kontomeny för ${user.username}`}
        className="flex w-full items-center gap-2.5 rounded-lg p-2 text-left text-sm transition-colors outline-none hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring data-[state=open]:bg-sidebar-accent"
      >
        <Avatar className="size-8 rounded-lg after:rounded-lg">
          <AvatarFallback className="rounded-lg bg-brand-soft text-xs font-semibold text-brand">
            {initials}
          </AvatarFallback>
        </Avatar>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{user.username}</span>
          <span className="block truncate text-xs text-muted-foreground">Inloggad</span>
        </span>
        <ChevronsUpDown className="size-4 text-muted-foreground" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="top"
        align="start"
        className="w-(--radix-dropdown-menu-trigger-width) min-w-56"
      >
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          Tema
        </DropdownMenuLabel>
        {THEMES.map(({ value, label, icon: Icon }) => (
          <DropdownMenuItem key={value} onSelect={() => setTheme(value)}>
            <Icon aria-hidden />
            {label}
            {theme === value && <Check className="ml-auto" aria-hidden />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onLogout}>
          <LogOut aria-hidden />
          Logga ut
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
