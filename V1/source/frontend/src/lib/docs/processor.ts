import { unified } from "unified"
import remarkParse from "remark-parse"
import remarkGfm from "remark-gfm"
import remarkRehype from "remark-rehype"
import rehypeSlug from "rehype-slug"
import rehypeHighlight from "rehype-highlight"
import rehypeSanitize, { defaultSchema } from "rehype-sanitize"
import type { Schema } from "hast-util-sanitize"
import rehypeStringify from "rehype-stringify"

export interface TocItem {
  id: string
  text: string
  level: 2 | 3
}

// Extend the default schema:
//   - id is already globally allowed via defaultSchema.attributes["*"]
//   - Add hljs* className to code, span, pre (syntax highlighting classes)
const safeSchema: Schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    // Allow language-* AND hljs* on <code> (rehype-highlight adds both)
    code: [["className", /^language-/, /^hljs/]],
    // Allow hljs-* on <span> (inline syntax tokens)
    span: [["className", /^hljs/]],
    // Allow language-* on <pre> (wrapper class)
    pre: [["className", /^language-/, /^hljs/]],
  },
}

/** Run the full unified pipeline: md → hast → sanitized HTML */
export async function processMarkdown(content: string): Promise<string> {
  const result = await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype, { allowDangerousHtml: false })
    .use(rehypeSlug)
    .use(rehypeHighlight, { detect: true })
    .use(rehypeSanitize, safeSchema)
    .use(rehypeStringify)
    .process(content)
  return String(result)
}

/** Extract H2/H3 headings from raw markdown for TOC generation.
 *  Uses the same slug algorithm as rehype-slug (github-slugger compatible). */
export function extractToc(markdown: string): TocItem[] {
  const items: TocItem[] = []
  const seen: Record<string, number> = {}

  for (const line of markdown.split("\n")) {
    const m = line.match(/^(#{2,3})\s+(.+)$/)
    if (!m) continue
    const level = m[1]!.length as 2 | 3
    // Strip inline code backticks and bold/italic markers for display text
    const text = m[2]!
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .trim()

    // Replicate github-slugger: lowercase, keep CJK + word chars + hyphens
    const raw = text.toLowerCase().replace(/\s+/g, "-").replace(/[^\w\u4e00-\u9fa5-]/g, "")
    const count = seen[raw] ?? 0
    seen[raw] = count + 1
    const id = count === 0 ? raw : `${raw}-${count}`

    items.push({ id, text, level })
  }
  return items
}
