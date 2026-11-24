import { CircleAlert, RotateCcw } from "lucide-react"

import { BrandMark } from "@/components/brand"
import { AgentActivity } from "@/components/chat/agent-activity"
import { CopyButton } from "@/components/chat/copy-button"
import { Markdown } from "@/components/chat/markdown"
import { SourceCards } from "@/components/chat/source-cards"
import { Button } from "@/components/ui/button"
import type { AssistantMessage as AssistantMessageData } from "@/lib/types"

/** One answer: the agent's steps, the streamed Markdown, the cited sources, and copy or retry. */
export function AssistantMessage({
  message,
  onRetry,
}: {
  message: AssistantMessageData
  onRetry: (id: string) => void
}) {
  const working = message.status === "streaming"
  const answering = message.content.length > 0

  return (
    <article className="flex gap-3" aria-busy={working} aria-label="Svar">
      <BrandMark size="sm" className="mt-0.5" />
      <div className="min-w-0 flex-1 space-y-3">
        <AgentActivity activity={message.activity} working={working} answering={answering} />

        {answering && <Markdown>{message.content}</Markdown>}

        {message.status === "error" && (
          <p
            className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            role="alert"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            {message.error}
          </p>
        )}
        {message.status === "stopped" && (
          <p className="text-sm text-muted-foreground italic">Svaret stoppades.</p>
        )}

        {message.status === "done" && <SourceCards sources={message.sources} />}

        {!working && (
          <div className="-ml-1.5 flex items-center gap-1 text-muted-foreground">
            {answering && message.status === "done" && <CopyButton text={message.content} />}
            {(message.status === "error" || message.status === "stopped") && (
              <Button variant="outline" size="sm" onClick={() => onRetry(message.id)}>
                <RotateCcw aria-hidden />
                Försök igen
              </Button>
            )}
          </div>
        )}
      </div>
    </article>
  )
}
