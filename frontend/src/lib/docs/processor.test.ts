import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { extractToc, processMarkdown } from "./processor"

describe("design document navigation", () => {
  it("links every architecture section to its sanitized rendered heading", async () => {
    const markdown = readFileSync(
      resolve(process.cwd(), "../docs/specs/pentest-sandbox-redesign.md"), "utf-8"
    )
    const html = await processMarkdown(markdown)
    const document = new DOMParser().parseFromString(html, "text/html")
    const items = extractToc(markdown)
    expect(items.length).toBeGreaterThan(10)
    for (const item of items) {
      expect(document.getElementById(item.id)?.textContent).toBe(item.text)
    }
  })
})
