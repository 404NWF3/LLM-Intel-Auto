import Link from "next/link"
import type { DocMeta } from "@/lib/docs/registry"
import styles from "./DocCard.module.css"

const CATEGORY_CLASS: Record<string, string> = {
  "WP1-1 智能体": styles.catWp11 ?? "",
  数据库: styles.catDb ?? "",
  前端设计: styles.catFrontend ?? "",
}

interface DocCardProps {
  doc: DocMeta
}

export function DocCard({ doc }: DocCardProps) {
  return (
    <Link href={`/docs/${doc.slug}`} className={styles.card}>
      <div className={styles.top}>
        <span className={`${styles.catBadge ?? ""} ${CATEGORY_CLASS[doc.category] ?? ""}`}>
          {doc.category}
        </span>
        <h3 className={styles.title}>{doc.title}</h3>
        <p className={styles.description}>{doc.description}</p>
      </div>

      {doc.sourceFiles.length > 0 && (
        <div className={styles.files}>
          <span className={styles.filesLabel}>文件映射</span>
          <div className={styles.chips}>
            {doc.sourceFiles.map((f) => (
              <span key={f.path} className={styles.chip} title={f.path}>
                {f.label ?? f.path.split("/").filter(Boolean).pop() ?? f.path}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className={styles.tags}>
        {doc.tags.slice(0, 4).map((tag) => (
          <span key={tag} className={styles.tag}>
            {tag}
          </span>
        ))}
      </div>
    </Link>
  )
}
