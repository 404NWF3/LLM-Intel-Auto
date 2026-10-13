import styles from "./DocRenderer.module.css"

interface DocRendererProps {
  /** Pre-processed, rehype-sanitize–cleaned HTML string */
  html: string
}

/** Renders sanitized markdown HTML. The `html` prop MUST come from
 *  `processMarkdown()` in lib/docs/processor.ts which runs rehype-sanitize. */
export function DocRenderer({ html }: DocRendererProps) {
  return (
    <div
      className={styles.prose}
      // Safe: content has been sanitized server-side via rehype-sanitize
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
