import styles from "./CodeWindow.module.css"

interface CodeWindowProps {
  children: React.ReactNode
  /** 可选标题，显示在 bar 中间 */
  title?: string
  className?: string
}

export function CodeWindow({ children, title, className }: CodeWindowProps) {
  return (
    <div className={[styles.window, className].filter(Boolean).join(" ")}>
      <div className={styles.bar}>
        <span className={styles.dot} aria-hidden="true" />
        <span className={styles.dot} aria-hidden="true" />
        <span className={styles.dot} aria-hidden="true" />
        {title && <span className={styles.title}>{title}</span>}
      </div>
      <div className={styles.body}>{children}</div>
    </div>
  )
}
