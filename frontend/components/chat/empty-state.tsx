import { Building2, FileText, MapPin, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react"

import { BrandMark } from "@/components/brand"

type Suggestion = { question: string; topic: string; icon: LucideIcon }

const SUGGESTION_CARDS: Suggestion[] = [
  { question: "Vad erbjuder ni för typer av AI-tjänster?", topic: "Tjänster", icon: Sparkles },
  { question: "Vilka branscher jobbar ni med?", topic: "Kunder", icon: Building2 },
  { question: "Hur kontaktar man er, och var sitter ni?", topic: "Kontakt", icon: MapPin },
  {
    question: "Har ni beskrivit hur ni jobbar med säkerhet/sekretess?",
    topic: "Säkerhet",
    icon: ShieldCheck,
  },
  {
    question: "Sammanfatta sidan 'Om oss' i tre punkter och länka källan.",
    topic: "Om oss",
    icon: FileText,
  },
]

export const SUGGESTIONS = SUGGESTION_CARDS.map((s) => s.question)

export function EmptyState({
  username,
  onPick,
}: {
  username?: string
  onPick: (question: string) => void
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center py-12 text-center">
      <BrandMark size="lg" className="mb-5" />
      <h2 className="text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
        {username ? `Hej ${username}, vad vill du veta?` : "Vad vill du veta?"}
      </h2>
      <p className="mt-2 max-w-md text-sm text-pretty text-muted-foreground">
        Jag svarar utifrån innehållet på compileit.com och länkar alltid till källan. Finns svaret
        inte på webbplatsen säger jag det.
      </p>

      <ul className="mt-8 grid w-full max-w-2xl gap-2.5 text-left sm:grid-cols-2">
        {SUGGESTION_CARDS.map(({ question, topic, icon: Icon }, index) => (
          <li key={question} className={index === 4 ? "sm:col-span-2" : undefined}>
            <button
              type="button"
              onClick={() => onPick(question)}
              aria-label={question}
              className="group flex h-full w-full items-start gap-3 rounded-xl border bg-card p-3.5 text-left text-sm shadow-xs transition-all outline-none hover:-translate-y-px hover:border-brand/40 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/40 motion-reduce:hover:translate-y-0"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand transition-colors group-hover:bg-brand group-hover:text-brand-foreground">
                <Icon className="size-4" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-xs font-medium text-muted-foreground">{topic}</span>
                <span className="mt-0.5 block leading-snug text-foreground">{question}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
