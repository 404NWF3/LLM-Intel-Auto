"use client"

import { useWpAlerts } from "@/lib/hooks/useWpAlerts"
import styles from "./AlertPanel.module.css"

const SEVERITY_CLASS: Record<"HIGH" | "MEDIUM" | "LOW", string> = {
  HIGH: styles.severityHIGH ?? "",
  MEDIUM: styles.severityMEDIUM ?? "",
  LOW: styles.severityLOW ?? "",
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return "刚刚"
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

interface AlertPanelProps {
  wpId?: string
  title?: string
}

export function AlertPanel({ wpId, title = "安全告警" }: AlertPanelProps) {
  const { alerts, isLoading } = useWpAlerts(wpId)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>{title}</h2>
        {!isLoading && (
          <span className={styles.count}>{alerts.length} 条</span>
        )}
      </div>

      {isLoading ? (
        <div className={styles.empty}>加载中…</div>
      ) : alerts.length === 0 ? (
        <div className={styles.empty}>暂无告警</div>
      ) : (
        <ul className={styles.list}>
          {alerts.map((alert) => (
            <li key={alert.id} className={styles.item}>
              <span
                className={`${styles.severityBadge} ${SEVERITY_CLASS[alert.severity]}`}
              >
                {alert.severity}
              </span>
              <div className={styles.body}>
                <p className={styles.alertTitle}>{alert.title}</p>
                <div className={styles.meta}>
                  {alert.cvss !== undefined && (
                    <span>CVSS {alert.cvss.toFixed(1)}</span>
                  )}
                  <span>{timeAgo(alert.created_at)}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
