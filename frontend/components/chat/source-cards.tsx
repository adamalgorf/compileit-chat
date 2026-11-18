import { ArrowUpRight } from "lucide-react"

import { displayUrl } from "@/lib/activity"
import type { SourceLink } from "@/lib/types"

/** The pages the answer cites, as cards that open the page in a new tab. */
export function SourceCards({ sources }: { sources: SourceLink[] }) {
  if (!sources.length) return null
  return (
    <section aria-label="Källor" className="space-y-2">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Källor</h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {sources.map((source) => (
          <li key={source.url}>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex h-full items-start justify-between gap-3 rounded-lg border bg-card px-3 py-2.5 transition-colors outline-none hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <span className="min-w-0">
                <span className="line-clamp-2 text-sm font-medium">{source.title}</span>
                <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                  {displayUrl(source.url)}
                </span>
              </span>
              <ArrowUpRight
                className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
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
