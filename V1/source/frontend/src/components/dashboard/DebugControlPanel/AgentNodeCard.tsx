import type { WpNodeInfo, WpNodeLastStatus } from "@/lib/types/dashboard"
import styles from "./DebugControlPanel.module.css"

interface AgentNodeCardProps {
  node: WpNodeInfo
  index: number
  isTriggering: boolean
  onTrigger: (nodeName: string) => Promise<void>
}

const STATUS_DOT_CLASS: Record<WpNodeLastStatus, string> = {
  running: styles.dotRunning ?? "",
  succeeded: styles.dotSucceeded ?? "",
  failed: styles.dotFailed ?? "",
  skipped: styles.dotSkipped ?? "",
  never_run: styles.dotNeverRun ?? "",
}

const STATUS_CARD_CLASS: Record<WpNodeLastStatus, string> = {
  running: styles.nodeCardRunning ?? "",
  succeeded: styles.nodeCardSucceeded ?? "",
  failed: styles.nodeCardFailed ?? "",
  skipped: styles.nodeCardSkipped ?? "",
  never_run: "",
}

const STATUS_LABELS_ZH: Record<WpNodeLastStatus, string> = {
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  skipped: "已跳过",
  never_run: "未运行",
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "刚刚"
  if (minutes < 60) return `${minutes}m 前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h 前`
  return `${Math.floor(hours / 24)}d 前`
}

export function AgentNodeCard({
  node,
  index,
  isTriggering,
  onTrigger,
}: AgentNodeCardProps) {
  const cardClass = STATUS_CARD_CLASS[node.last_status]

  return (
    <div className={`${styles.nodeCard} ${cardClass}`}>
      <span className={styles.nodeIndex}>{String(index + 1).padStart(2, "0")}</span>
      <span
        className={`${styles.nodeStatusDot} ${STATUS_DOT_CLASS[node.last_status]}`}
        title={STATUS_LABELS_ZH[node.last_status]}
      />
      <div className={styles.nodeInfo}>
        <p className={styles.nodeName}>{node.display_name}</p>
        {node.description && <p className={styles.nodeDesc}>{node.description}</p>}
        <p className={styles.nodeLastRun}>
          {node.last_run_at
            ? `上次运行：${timeAgo(node.last_run_at)} · ${STATUS_LABELS_ZH[node.last_status]}`
            : STATUS_LABELS_ZH[node.last_status]}
        </p>
      </div>
      <button
        className={styles.nodeTriggerBtn}
        disabled={!node.is_triggerable || isTriggering}
        onClick={() => void onTrigger(node.node_name)}
        title={
          !node.is_triggerable
            ? "该节点不支持单独触发"
            : `单独运行 ${node.node_name}`
        }
      >
        {isTriggering ? "运行中..." : "单独运行"}
      </button>
    </div>
  )
}
