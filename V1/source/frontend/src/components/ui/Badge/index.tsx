import type { WpStatus } from "@/lib/types/wp"
import styles from "./Badge.module.css"

type BadgeVariant = WpStatus | "generic" | "user"

interface BadgeProps {
  variant: BadgeVariant
  children: React.ReactNode
  className?: string
}

const VARIANT_LABELS: Record<BadgeVariant, string> = {
  running: "运行中",
  idle: "空闲",
  warning: "告警",
  error: "错误",
  pending: "待接入",
  generic: "通用层",
  user: "用户层",
}

export function Badge({ variant, children, className }: BadgeProps) {
  return (
    <span
      className={[styles.badge, styles[variant], className].filter(Boolean).join(" ")}
      aria-label={VARIANT_LABELS[variant]}
    >
      {children}
    </span>
  )
}
