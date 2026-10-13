import type { Metadata } from "next"
import { DOC_REGISTRY, DOC_CATEGORIES } from "@/lib/docs/registry"
import { DocCard } from "@/components/docs/DocCard"
import styles from "./page.module.css"

export const metadata: Metadata = {
  title: "技术文档 — SUFE-SAADS",
  description: "SUFE-SAADS 系统的技术文档：智能体架构、数据库设计与前端方案。",
}

export default function DocsPage() {
  return (
    <div className={styles.page}>
      <div className={`container ${styles.inner ?? ""}`}>
        {/* Page header */}
        <header className={styles.header}>
          <h1 className={styles.heading}>技术文档</h1>
          <p className={styles.subheading}>
            覆盖 WP1-1 智能体架构、数据库模块设计与前端开发方案的完整技术参考。
          </p>
          <div className={styles.stats}>
            <span>{DOC_REGISTRY.length} 篇文档</span>
            <span aria-hidden="true">·</span>
            <span>{DOC_CATEGORIES.length} 个分类</span>
          </div>
        </header>

        {/* Grouped by category */}
        <main>
          {DOC_CATEGORIES.map((category) => {
            const docs = DOC_REGISTRY.filter((d) => d.category === category)
            return (
              <section key={category} className={styles.section}>
                <div className={styles.sectionHeader}>
                  <h2 className={styles.sectionTitle}>{category}</h2>
                  <span className={styles.sectionCount}>{docs.length} 篇</span>
                </div>
                <div className={styles.grid}>
                  {docs.map((doc) => (
                    <DocCard key={doc.slug} doc={doc} />
                  ))}
                </div>
              </section>
            )
          })}
        </main>
      </div>
    </div>
  )
}
