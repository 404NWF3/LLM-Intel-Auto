import styles from "./SkeletonLine.module.css"

interface SkeletonLineProps {
  /** CSS 宽度值，如 "80%"、"12ch" */
  width?: string
  /** CSS 高度值，默认 "0.85em" */
  height?: string
  className?: string
}

export function SkeletonLine({
  width = "100%",
  height,
  className,
}: SkeletonLineProps) {
  return (
    <span
      className={[styles.line, className].filter(Boolean).join(" ")}
      style={{
        width,
        ...(height ? { height } : {}),
      }}
      aria-hidden="true"
    />
  )
}

/** 多行骨架屏（常用于卡片占位） */
export function SkeletonBlock({
  lines = 3,
  className,
}: {
  lines?: number
  className?: string
}) {
  const widths = ["100%", "88%", "72%", "95%", "60%"]
  return (
    <div
      className={[styles.block, className].filter(Boolean).join(" ")}
      aria-busy="true"
      aria-label="加载中"
    >
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonLine key={i} width={widths[i % widths.length]} />
      ))}
    </div>
  )
}
