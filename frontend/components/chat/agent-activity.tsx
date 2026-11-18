import { Check, LoaderCircle } from "lucide-react"

import { describeActivity } from "@/lib/activity"
import { cn } from "@/lib/utils"
import type { ToolActivity } from "@/lib/types"

/**
 * What the agent is doing, e.g. «Söker på webbplatsen: "AI-tjänster"», as small pills. While
 * the answer is pending the latest step spins; afterwards the steps stay as a checked trail.
 */
export function AgentActivity({
  activity,
  working,
  answering,
}: {
  activity: ToolActivity[]
  /** The answer is still being produced. */
  working: boolean
  /** Answer text has started arriving. */
  answering: boolean
}) {
  if (!activity.length) {
    return working && !answering ? <Step label="Tänker" active /> : null
  }
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Agentens steg">
      {activity.map((step, index) => (
        <li key={index}>
          <Step
            label={describeActivity(step)}
            active={working && !answering && index === activity.length - 1}
          />
        </li>
      ))}
    </ul>
  )
}

function Step({ label, active = false }: { label: string; active?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
        active
          ? "border-brand/30 bg-brand-soft text-brand"
          : "border-border bg-muted/50 text-muted-foreground",
      )}
    >
      {active ? (
        <LoaderCircle className="size-3 animate-spin motion-reduce:animate-none" aria-hidden />
      ) : (
        <Check className="size-3" aria-hidden />
      )}
      <span className="truncate">
        {label}
        {active && "…"}
      </span>
    </span>
  )
}
