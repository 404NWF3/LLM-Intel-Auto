"use client"

import { useWpStatus } from "@/lib/hooks/useWpStatus"
import { SORTED_WP_REGISTRY } from "@/lib/wp-registry"
import styles from "./SystemHealthBar.module.css"

function useSystemStats() {
  const s11 = useWpStatus("wp11")
  const s12 = useWpStatus("wp12")
  const s13 = useWpStatus("wp13")
  const s14 = useWpStatus("wp14")

  const statuses = [s11, s12, s13, s14].map((s) => s.data?.status ?? "pending")
  const running = statuses.filter((s) => s === "running").length
  const warning = statuses.filter((s) => s === "warning").length
  const error = statuses.filter((s) => s === "error").length

  return { running, warning, error }
}

export function SystemHealthBar() {
  const { running, warning, error } = useSystemStats()
  const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })

  return (
    <div className={styles.bar}>
      <span className={styles.label}>系统状态</span>
      <div className={`${styles.stat} ${styles.statRunning}`}>
        <span className={`${styles.dot} ${styles.dotRunning}`} />
        <span className={styles.statValue}>{running}</span>
        <span>运行中</span>
      </div>
      <div className={styles.sep} />
      <div className={`${styles.stat} ${styles.statWarning}`}>
        <span className={`${styles.dot} ${styles.dotWarning}`} />
        <span className={styles.statValue}>{warning}</span>
        <span>告警</span>
      </div>
      <div className={styles.sep} />
      <div className={`${styles.stat} ${styles.statError}`}>
        <span className={`${styles.dot} ${styles.dotError}`} />
        <span className={styles.statValue}>{error}</span>
        <span>错误</span>
      </div>
      <div className={styles.sep} />
      <span className={styles.stat}>
        共 {SORTED_WP_REGISTRY.length} 个智能体
      </span>
      <span className={styles.lastSync}>最后同步 {now}</span>
    </div>
  )
}
