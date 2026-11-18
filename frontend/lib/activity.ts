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

/** "compileit.com/om-oss" from "https://www.compileit.com/om-oss/". Never throws. */
export function displayUrl(url: string): string {
  try {
    const { hostname, pathname } = new URL(url)
    return hostname.replace(/^www\./, "") + pathname.replace(/\/$/, "")
  } catch {
    return url
  }
}
