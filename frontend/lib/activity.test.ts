import { describe, expect, it } from "vitest"

import { describeActivity, displayUrl } from "@/lib/activity"

describe("describeActivity", () => {
  it.each([
    [{ tool: "search_website", query: "AI-tjänster" }, 'Söker på webbplatsen: "AI-tjänster"'],
    [{ tool: "get_page", query: "/om-oss" }, "Läser sidan /om-oss"],
    [{ tool: "list_pages", query: null }, "Går igenom webbplatsens sidor"],
    [{ tool: "unknown", query: null }, "Arbetar"],
  ])("describes %j", (activity, expected) => {
    expect(describeActivity(activity)).toBe(expected)
  })
})

describe("displayUrl", () => {
  it("shows domain and path without www or trailing slash", () => {
    expect(displayUrl("https://www.compileit.com/om-oss/")).toBe("compileit.com/om-oss")
  })

  it("falls back to the raw string instead of throwing on malformed URLs", () => {
    expect(displayUrl("not a url")).toBe("not a url")
  })
})
