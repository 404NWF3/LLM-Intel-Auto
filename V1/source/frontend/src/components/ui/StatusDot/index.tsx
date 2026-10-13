import type { WpStatus } from "@/lib/types/wp"
import styles from "./StatusDot.module.css"

interface StatusDotProps {
  status: WpStatus
  size?: "sm" | "md" | "lg"
  className?: string
}

export function StatusDot({ status, size = "md", className }: StatusDotProps) {
  return (
    <span
      className={[
        styles.dot,
        styles[status],
        styles[`size-${size}`],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={`状态：${status}`}
    />
  )
}
