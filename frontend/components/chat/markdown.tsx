import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

/**
 * Renders the agent's markdown safely: react-markdown never renders raw HTML (no
 * rehype-raw) and its default URL transform drops `javascript:` and similar schemes.
 * Links open in a new tab without giving the target page access to this one.
 */
const components: Components = {
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-foreground underline decoration-foreground/30 underline-offset-4 transition-colors hover:decoration-foreground"
    >
      {children}
    </a>
  ),
  p: ({ children }) => <p className="leading-7 [&:not(:first-child)]:mt-3">{children}</p>,
  ul: ({ children }) => <ul className="mt-3 ml-5 list-disc space-y-1.5">{children}</ul>,
  ol: ({ children }) => <ol className="mt-3 ml-5 list-decimal space-y-1.5">{children}</ol>,
  li: ({ children }) => <li className="leading-7 marker:text-muted-foreground">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  h1: ({ children }) => <h3 className="mt-4 font-semibold">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-4 font-semibold">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-4 font-semibold">{children}</h4>,
  code: ({ children }) => (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
  ),
}

/** Renders an answer as Markdown, safely (see above). */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-[15px] break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
