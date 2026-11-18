import { ArrowUpRight, Globe } from "lucide-react"

import { displayUrl } from "@/lib/activity"
import type { SourceLink } from "@/lib/types"

/** The pages the answer cites, as cards that open the page in a new tab. */
export function SourceCards({ sources }: { sources: SourceLink[] }) {
  if (!sources.length) return null
  return (
    <section aria-label="Källor" className="space-y-2 pt-1">
      <h3 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        Källor · {sources.length}
      </h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {sources.map((source) => (
          <li key={source.url}>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex h-full items-center gap-3 rounded-xl border bg-card p-2.5 pr-3 shadow-xs transition-all outline-none hover:border-brand/40 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/40"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground transition-colors group-hover:bg-brand-soft group-hover:text-brand">
                <Globe className="size-4" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-1 text-sm font-medium">{source.title}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {displayUrl(source.url)}
                </span>
              </span>
              <ArrowUpRight
                className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-brand"
                aria-hidden
              />
              <span className="sr-only">(öppnas i ny flik)</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
