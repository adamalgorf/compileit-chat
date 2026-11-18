import { Sparkles } from "lucide-react"

import { cn } from "@/lib/utils"

/** The app's mark: a brand-coloured tile with a spark, used in the sidebar, login and chat. */
export function BrandMark({
  size = "md",
  className,
}: {
  size?: "sm" | "md" | "lg"
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center bg-gradient-to-br from-brand to-brand/70 text-brand-foreground shadow-sm ring-1 ring-black/5 ring-inset",
        {
          sm: "size-6 rounded-md [&_svg]:size-3.5",
          md: "size-8 rounded-lg [&_svg]:size-4",
          lg: "size-12 rounded-xl [&_svg]:size-6",
        }[size],
        className,
      )}
    >
      <Sparkles />
    </span>
  )
}

export function BrandName({ className }: { className?: string }) {
  return (
    <span className={cn("flex min-w-0 flex-col leading-tight", className)}>
      <span className="truncate text-sm font-semibold tracking-tight">Compilo</span>
      <span className="truncate text-xs text-muted-foreground">Svarar utifrån compileit.com</span>
    </span>
  )
}
