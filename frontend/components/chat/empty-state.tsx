import { MessageSquareText } from "lucide-react"

export const SUGGESTIONS = [
  "Vad erbjuder ni för typer av AI-tjänster?",
  "Vilka branscher jobbar ni med?",
  "Hur kontaktar man er, och var sitter ni?",
  "Har ni beskrivit hur ni jobbar med säkerhet/sekretess?",
  "Sammanfatta sidan 'Om oss' i tre punkter och länka källan.",
] as const

export function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="flex flex-1 flex-col justify-center py-10">
      <div className="mb-8 space-y-3">
        <span className="flex size-10 items-center justify-center rounded-xl border bg-card">
          <MessageSquareText className="size-5" aria-hidden />
        </span>
        <h2 className="text-2xl font-semibold tracking-tight text-balance">Fråga om Compileit</h2>
        <p className="max-w-prose text-pretty text-muted-foreground">
          Jag svarar utifrån innehållet på compileit.com och länkar alltid till källan. Finns svaret
          inte på webbplatsen säger jag det.
        </p>
      </div>
      <h3 className="mb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Prova att fråga
      </h3>
      <ul className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onPick(question)}
              className="rounded-full border bg-card px-3.5 py-2 text-left text-sm transition-colors outline-none hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
