"use client"

import { useWpStatus } from "@/lib/hooks/useWpStatus"
import { StatusDot } from "@/components/ui/StatusDot"
import { STATUS_LABELS, formatUptime, type WpStatus } from "@/lib/types/wp"
import type { WpMeta } from "@/lib/wp-registry"
import styles from "./WpDetailHeader.module.css"

const STATUS_LABEL_CLASS: Record<WpStatus, string> = {
  running: styles.statusRunning ?? "",
  idle: styles.statusIdle ?? "",
  warning: styles.statusWarning ?? "",
  error: styles.statusError ?? "",
  pending: styles.statusPending ?? "",
}

interface WpDetailHeaderProps {
  wp: WpMeta
}

export function WpDetailHeader({ wp }: WpDetailHeaderProps) {
  const { data } = useWpStatus(wp.id)
  const status = data?.status ?? wp.mockStatus

  return (
    <div className={styles.header}>
      <div className={styles.top}>
        <div className={styles.titleGroup}>
          <div className={styles.code}>{wp.code}</div>
          <h1 className={styles.name}>{wp.label}</h1>
          <div className={styles.role}>{wp.description}</div>
        </div>

        <div className={styles.statusRow}>
          <StatusDot status={status} size="md" />
          <span className={`${styles.statusLabel} ${STATUS_LABEL_CLASS[status]}`}>
            {STATUS_LABELS[status]}
          </span>
        </div>
      </div>

      {data && (
        <>
          <div className={styles.meta}>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>运行时长</span>
              <span className={styles.metaValue}>{formatUptime(data.uptime_seconds)}</span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>版本</span>
              <span className={styles.metaValue}>{data.version}</span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>最后更新</span>
              <span className={styles.metaValue}>
                {new Date(data.last_updated).toLocaleTimeString("zh-CN")}
              </span>
            </div>
          </div>

          {data.current_tasks && data.current_tasks.length > 0 && (
            <div className={styles.tasks}>
              {data.current_tasks.map((task) => (
                <span key={task} className={styles.task}>{task}</span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
