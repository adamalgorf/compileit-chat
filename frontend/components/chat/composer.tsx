"use client"

import { ArrowUp, Square } from "lucide-react"
import { useEffect, useRef, useState, type KeyboardEvent } from "react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

/** Mirrors the backend's `MAX_QUESTION_LENGTH`. */
export const MAX_LENGTH = 2000

export function Composer({
  streaming,
  onSend,
  onStop,
}: {
  streaming: boolean
  onSend: (text: string) => void
  onStop: () => void
}) {
  const [text, setText] = useState("")
  const input = useRef<HTMLTextAreaElement>(null)
  const canSend = text.trim().length > 0 && !streaming

  // Refocus the input when an answer finishes, so the next question can be typed directly.
  // Not on mount: on phones that would pop up the keyboard over the empty state.
  const wasStreaming = useRef(streaming)
  useEffect(() => {
    if (wasStreaming.current && !streaming) input.current?.focus()
    wasStreaming.current = streaming
  }, [streaming])

  const submit = () => {
    if (!canSend) return
    onSend(text)
    setText("")
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter is a new line; never while an IME is composing.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  const nearLimit = text.length > MAX_LENGTH * 0.9

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
      className="relative rounded-2xl border bg-card shadow-sm transition-shadow focus-within:ring-3 focus-within:ring-ring/30"
    >
      <label htmlFor="question" className="sr-only">
        Din fråga
      </label>
      <Textarea
        id="question"
        ref={input}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ställ en fråga om Compileit…"
        maxLength={MAX_LENGTH}
        rows={1}
        className="max-h-48 min-h-12 resize-none border-0 bg-transparent py-3.5 pr-14 pl-4 text-[15px] shadow-none focus-visible:ring-0 dark:bg-transparent"
      />
      <div className="absolute right-2 bottom-2 flex items-center gap-2">
        {nearLimit && (
          <span className="text-xs text-muted-foreground tabular-nums" aria-live="polite">
            {text.length}/{MAX_LENGTH}
          </span>
        )}
        {streaming ? (
          <Button
            type="button"
            size="icon"
            variant="secondary"
            onClick={onStop}
            aria-label="Stoppa svaret"
          >
            <Square className="fill-current" aria-hidden />
          </Button>
        ) : (
          <Button type="submit" size="icon" disabled={!canSend} aria-label="Skicka fråga">
            <ArrowUp aria-hidden />
          </Button>
        )}
      </div>
    </form>
  )
}
