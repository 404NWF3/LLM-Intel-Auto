"use client"

import Link from "next/link"
import { useWpStatus } from "@/lib/hooks/useWpStatus"
import { StatusDot } from "@/components/ui/StatusDot"
import { STATUS_LABELS, formatUptime, type WpStatus } from "@/lib/types/wp"
import type { WpMeta } from "@/lib/wp-registry"
import styles from "./WpStatusCard.module.css"

const STATUS_BADGE_CLASS: Record<WpStatus, string> = {
  running: styles.statusRunning ?? "",
  idle: styles.statusIdle ?? "",
  warning: styles.statusWarning ?? "",
  error: styles.statusError ?? "",
  pending: styles.statusPending ?? "",
}

interface WpStatusCardProps {
  wp: WpMeta
}

export function WpStatusCard({ wp }: WpStatusCardProps) {
  const { data, isLoading } = useWpStatus(wp.id)
  const status = data?.status ?? wp.mockStatus

  const isPending = status === "pending"

  return (
    <Link
      href={`/dashboard/${wp.id}`}
      className={`${styles.card} ${isPending ? styles.cardPending : ""}`}
    >
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <span className={styles.code}>{wp.code}</span>
          <h3 className={styles.name}>{wp.label}</h3>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.375rem" }}>
          <StatusDot status={status} size="md" />
          <span className={`${styles.statusBadge} ${STATUS_BADGE_CLASS[status]}`}>
            {STATUS_LABELS[status]}
          </span>
        </div>
      </div>

      <div className={styles.metrics}>
        {isLoading ? (
          <>
            <div className={styles.skeleton} style={{ width: "80%" }} />
            <div className={styles.skeleton} style={{ width: "65%" }} />
            <div className={styles.skeleton} style={{ width: "72%" }} />
          </>
        ) : (
          wp.metrics.map((m) => {
            const rawVal = data?.metrics[m.key]
            const val =
              rawVal === undefined
                ? "—"
                : m.format === "percent"
                  ? `${Number(rawVal).toFixed(1)}%`
                  : String(rawVal)
            return (
              <div key={m.key} className={styles.metricRow}>
                <span className={styles.metricLabel}>{m.label}</span>
                <span className={styles.metricValue}>
                  {val}
                  {rawVal !== undefined && m.unit ? ` ${m.unit}` : ""}
                </span>
              </div>
            )
          })
        )}
      </div>

      <div className={styles.footer}>
        <span>{wp.role}</span>
        {data ? (
          <span>运行 {formatUptime(data.uptime_seconds)}</span>
        ) : (
          <span>待接入</span>
        )}
      </div>
    </Link>
  )
}
