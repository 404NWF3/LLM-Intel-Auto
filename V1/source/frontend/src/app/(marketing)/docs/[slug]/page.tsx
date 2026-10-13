import { notFound } from "next/navigation"
import type { Metadata } from "next"
import path from "path"
import fs from "fs/promises"
import Link from "next/link"
import { ChevronLeft } from "lucide-react"
import { DOC_REGISTRY, findDoc } from "@/lib/docs/registry"
import { processMarkdown, extractToc } from "@/lib/docs/processor"
import { DocRenderer } from "@/components/docs/DocRenderer"
import { DocToc } from "@/components/docs/DocToc"
import styles from "./page.module.css"

interface PageProps {
  params: Promise<{ slug: string }>
}

/** Pregenerate all doc pages at build time */
export function generateStaticParams() {
  return DOC_REGISTRY.map((doc) => ({ slug: doc.slug }))
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params
  const doc = findDoc(slug)
  if (!doc) return {}
  return {
    title: `${doc.title} — SUFE-SAADS 文档`,
    description: doc.description,
  }
}

const DOCS_DIR = path.join(process.cwd(), "..", "docs")

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params
  const doc = findDoc(slug)
  if (!doc) notFound()

  const filePath = path.join(DOCS_DIR, doc.filename)
  let content: string
  try {
    content = await fs.readFile(filePath, "utf-8")
  } catch {
    notFound()
  }

  const [html, toc] = await Promise.all([processMarkdown(content), Promise.resolve(extractToc(content))])

  const CATEGORY_CLASS: Record<string, string> = {
    "WP1-1 智能体": styles.catWp11 ?? "",
    数据库: styles.catDb ?? "",
    前端设计: styles.catFrontend ?? "",
  }

  return (
    <div className={styles.page}>
      <div className={`container ${styles.inner ?? ""}`}>
        {/* Back link */}
        <Link href="/docs" className={styles.back}>
          <ChevronLeft width={16} height={16} aria-hidden="true" />
          返回文档列表
        </Link>

        {/* Doc header */}
        <header className={styles.docHeader}>
          <div className={styles.docMeta}>
            <span
              className={`${styles.catBadge ?? ""} ${CATEGORY_CLASS[doc.category] ?? ""}`}
            >
              {doc.category}
            </span>
            {doc.tags.slice(0, 3).map((tag) => (
              <span key={tag} className={styles.tag}>
                {tag}
              </span>
            ))}
          </div>
          <h1 className={styles.docTitle}>{doc.title}</h1>
          <p className={styles.docDescription}>{doc.description}</p>

          {/* File mapping */}
          {doc.sourceFiles.length > 0 && (
            <div className={styles.fileMap}>
              <span className={styles.fileMapLabel}>文件映射</span>
              <div className={styles.fileChips}>
                {doc.sourceFiles.map((f) => (
                  <span key={f.path} className={styles.fileChip} title={f.path}>
                    <span className={styles.fileChipLabel}>{f.label}</span>
                    <code className={styles.fileChipPath}>{f.path}</code>
                  </span>
                ))}
              </div>
            </div>
          )}
        </header>

        {/* Content + TOC */}
        <div className={styles.layout}>
          <article className={styles.article}>
            <DocRenderer html={html} />
          </article>

          {toc.length > 0 && (
            <aside className={styles.aside}>
              <DocToc items={toc} />
            </aside>
          )}
        </div>
      </div>
    </div>
  )
}
