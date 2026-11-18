import type { ToolActivity } from "@/lib/types"

/** Human-readable Swedish description of what the agent is doing. */
export function describeActivity({ tool, query }: ToolActivity): string {
  switch (tool) {
    case "search_website":
      return query ? `Söker på webbplatsen: "${query}"` : "Söker på webbplatsen"
    case "get_page":
      return query ? `Läser sidan ${query}` : "Läser en sida"
    case "list_pages":
      return "Går igenom webbplatsens sidor"
    default:
      return "Arbetar"
  }
}

/** "compileit.com" from "https://www.compileit.com/om-oss". */
export function displayDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}
