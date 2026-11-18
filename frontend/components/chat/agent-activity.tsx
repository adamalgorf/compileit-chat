import { Check, LoaderCircle } from "lucide-react"

import { describeActivity } from "@/lib/activity"
import type { ToolActivity } from "@/lib/types"

/**
 * What the agent is doing, e.g. «Söker på webbplatsen: "AI-tjänster"». While the answer
 * streams, the latest step spins; afterwards the steps stay as a compact, checked trail.
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
    <ul className="space-y-1" aria-label="Agentens steg">
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
    <span className="flex items-center gap-2 text-sm text-muted-foreground">
      {active ? (
        <LoaderCircle className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
      ) : (
        <Check className="size-3.5" aria-hidden />
      )}
      <span className={active ? "animate-pulse motion-reduce:animate-none" : undefined}>
        {label}
        {active && "…"}
      </span>
    </span>
  )
}
