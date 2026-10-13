"use client"

import { useCallback } from "react"
import type { RowComponentProps } from "react-window"
import type { WpVerboseLogEntry } from "@/lib/types/wp"
import styles from "./LogViewer.module.css"

export interface LogRowData {
  entries: WpVerboseLogEntry[]
  expandedSet: Set<number>
  onToggle: (index: number) => void
}

const LEVEL_ROW_CLASS: Record<string, string> = {
  DEBUG: styles.rowDEBUG ?? "",
  INFO: styles.rowINFO ?? "",
  WARN: styles.rowWARN ?? "",
  ERROR: styles.rowERROR ?? "",
}

const LEVEL_TAG_CLASS: Record<string, string> = {
  DEBUG: styles.levelTagDEBUG ?? "",
  INFO: styles.levelTagINFO ?? "",
  WARN: styles.levelTagWARN ?? "",
  ERROR: styles.levelTagERROR ?? "",
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return iso.slice(11, 19)
  }
}

function copyText(text: string) {
  void navigator.clipboard?.writeText(text)
}

function formatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

export function LogRow({
  index,
  style,
  entries,
  expandedSet,
  onToggle,
}: RowComponentProps<LogRowData>) {
  const entry = entries[index]
  if (!entry) return null

  const isVerbose = !!entry.verboseJson
  const isExpanded = isVerbose && expandedSet.has(index)

  const rowClass = LEVEL_ROW_CLASS[entry.level] ?? ""
  const tagClass = LEVEL_TAG_CLASS[entry.level] ?? ""

  const handleClick = useCallback(() => {
    if (isVerbose) {
      onToggle(index)
    } else {
      const text = `[${entry.timestamp}] [${entry.level}] [${entry.source}] ${entry.message}`
      copyText(text)
    }
  }, [isVerbose, index, onToggle, entry])

  const handleCopyJson = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (entry.verboseJson) {
      copyText(formatJson(entry.verboseJson))
    }
  }, [entry.verboseJson])

  if (isExpanded) {
    return (
      <div style={style} className={`${styles.rowExpanded ?? ""} ${rowClass}`}>
        <div className={styles.rowExpandedHeader ?? ""} onClick={handleClick}>
          <span className={styles.rowTime ?? ""}>{formatTime(entry.timestamp)}</span>
          <span className={`${styles.levelTag ?? ""} ${tagClass}`}>{entry.level}</span>
          <span className={styles.rowSource ?? ""}>{entry.source}</span>
          <span className={styles.rowMsg ?? ""}>{entry.verboseKey}:</span>
          <span className={styles.expandToggle ?? ""}>▼ 收起</span>
          <button className={styles.copyJsonBtn ?? ""} onClick={handleCopyJson} title="复制 JSON">
            复制
          </button>
        </div>
        <pre className={styles.verboseJson ?? ""}>
          {formatJson(entry.verboseJson!)}
          {entry.truncated ? "\n…(已截断)" : ""}
        </pre>
      </div>
    )
  }

  return (
    <div
      style={style}
      className={`${styles.row ?? ""} ${rowClass}`}
      onClick={handleClick}
      title={isVerbose ? "点击展开完整 JSON" : "点击复制日志行"}
      role="row"
    >
      <span className={styles.rowTime ?? ""}>{formatTime(entry.timestamp)}</span>
      <span className={`${styles.levelTag ?? ""} ${tagClass}`}>{entry.level}</span>
      <span className={styles.rowSource ?? ""}>{entry.source}</span>
      <span className={styles.rowMsg ?? ""}>
        {isVerbose && <span className={styles.expandToggle ?? ""}>▶ </span>}
        {entry.message}
      </span>
    </div>
  )
}
