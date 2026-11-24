"use client"

import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

/** Light/dark switch for the login screen; in the app, the account menu has the theme. */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const label = "Växla mellan ljust och mörkt läge"
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={label}
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          {/* Both icons are rendered and swapped with CSS, so server and client markup match. */}
          <Sun className="hidden dark:block" aria-hidden />
          <Moon className="dark:hidden" aria-hidden />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
