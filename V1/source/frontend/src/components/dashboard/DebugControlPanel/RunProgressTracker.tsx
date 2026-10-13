import type { WpRunStatus } from "@/lib/types/dashboard"
import styles from "./DebugControlPanel.module.css"

interface RunProgressTrackerProps {
  run: WpRunStatus
}

const STATUS_LABELS_ZH: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  partial_success: "部分成功",
  succeeded: "已完成",
  failed: "失败",
}

export function RunProgressTracker({ run }: RunProgressTrackerProps) {
  const { progress, status, errors } = run
  const isDone = status === "succeeded" || status === "partial_success"
  const isFailed = status === "failed"

  const fillClass = isFailed
    ? styles.progressFillFailed
    : isDone
      ? styles.progressFillDone
      : ""

  return (
    <div className={styles.progressWrap}>
      <div className={styles.progressHeader}>
        <span>
          {STATUS_LABELS_ZH[status] ?? status}
          {" · "}
          <span className={styles.progressCurrentNode}>
            {progress.current_node ?? "—"}
          </span>
        </span>
        <span>
          {progress.completed_nodes.length}/{progress.total_nodes} 节点 ·{" "}
          {progress.percent.toFixed(0)}%
        </span>
      </div>

      <div className={styles.progressBar}>
        <div
          className={`${styles.progressFill} ${fillClass}`}
          style={{ width: `${progress.percent}%` }}
        />
      </div>

      {errors.length > 0 && (
        <ul className={styles.errorList}>
          {errors.map((err, i) => (
            <li key={i} className={styles.errorItem}>
              [{err.node_name}] {err.error_type}: {err.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
