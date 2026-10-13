"use client"

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react"
import { List, useListRef } from "react-window"
import { useSSELog } from "@/lib/hooks/useSSELog"
import type { WpVerboseLogEntry } from "@/lib/types/wp"
import { LogRow, type LogRowData } from "./LogRow"
import styles from "./LogViewer.module.css"

const ROW_HEIGHT = 24
const EXPANDED_HEIGHT = 340  // 24px header + ~316px JSON block
const LIST_HEIGHT = 400

const LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"] as const
type Level = (typeof LEVELS)[number]

const STATUS_PILL_CLASS: Record<string, string> = {
  connecting: styles.statusConnecting ?? "",
  connected: styles.statusConnected ?? "",
  reconnecting: styles.statusReconnecting ?? "",
  error: styles.statusError ?? "",
  closed: styles.statusClosed ?? "",
}

const STATUS_LABELS_MAP: Record<string, string> = {
  connecting: "连接中",
  connected: "已连接",
  reconnecting: "重连中",
  error: "连接失败",
  closed: "已断开",
}

interface LogViewerProps {
  streamUrl: string
  height?: number
}

export function LogViewer({ streamUrl, height = LIST_HEIGHT }: LogViewerProps) {
  const [levelFilter, setLevelFilter] = useState<Set<Level>>(new Set(LEVELS))
  const [sourceFilter, setSourceFilter] = useState("")
  const [autoScroll, setAutoScroll] = useState(true)
  const [expandedSet, setExpandedSet] = useState<Set<number>>(new Set())
  const listRef = useListRef(null)

  const { entries, status, retryCount, reconnect, clear } = useSSELog(streamUrl)

  // Filter entries
  const filtered: WpVerboseLogEntry[] = useMemo(() => {
    return entries.filter((e) => {
      if (!levelFilter.has(e.level as Level)) return false
      if (sourceFilter && !e.source.toLowerCase().includes(sourceFilter.toLowerCase()))
        return false
      return true
    })
  }, [entries, levelFilter, sourceFilter])

  // Reset expanded set when filter changes (indices shift)
  useEffect(() => {
    setExpandedSet(new Set())
  }, [levelFilter, sourceFilter])

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (autoScroll && filtered.length > 0 && listRef.current) {
      listRef.current.scrollToRow({ index: filtered.length - 1, align: "end" })
    }
  }, [filtered.length, autoScroll, listRef])

  const toggleLevel = useCallback((level: Level) => {
    setLevelFilter((prev) => {
      const next = new Set(prev)
      if (next.has(level)) {
        next.delete(level)
      } else {
        next.add(level)
      }
      return next
    })
  }, [])

  const handleToggle = useCallback((index: number) => {
    setExpandedSet((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }, [])

  const handleClear = useCallback(() => {
    clear()
    setExpandedSet(new Set())
  }, [clear])

  const rowProps: LogRowData = useMemo(
    () => ({ entries: filtered, expandedSet, onToggle: handleToggle }),
    [filtered, expandedSet, handleToggle]
  )

  const getRowHeight = useCallback(
    (index: number) => {
      if (expandedSet.has(index) && filtered[index]?.verboseJson) {
        // Estimate height from JSON content lines
        const json = filtered[index].verboseJson!
        const lineCount = Math.min(json.split("\n").length + 5, 20)
        return Math.max(ROW_HEIGHT + lineCount * 16, EXPANDED_HEIGHT)
      }
      return ROW_HEIGHT
    },
    [expandedSet, filtered]
  )

  return (
    <div className={styles.viewer ?? ""}>
      {/* Header */}
      <div className={styles.header ?? ""}>
        <h2 className={styles.title ?? ""}>实时日志</h2>
        <span className={`${styles.statusPill ?? ""} ${STATUS_PILL_CLASS[status] ?? ""}`}>
          {STATUS_LABELS_MAP[status]}
        </span>
        {(status === "reconnecting" || status === "error") && retryCount > 0 && (
          <span style={{ fontSize: "0.7rem", color: "var(--text-faint)" }}>
            {status === "error" ? "已达最大重试次数" : `第 ${retryCount} 次重连`}
          </span>
        )}
        {status === "error" && (
          <button className={styles.reconnectBtn ?? ""} onClick={reconnect}>
            手动重连
          </button>
        )}
        <span style={{ marginLeft: "auto", fontSize: "0.7rem", color: "var(--text-faint)", fontFamily: "var(--font-mono)" }}>
          {filtered.length} / {entries.length}
        </span>
      </div>

      {/* Filter bar */}
      <div className={styles.filterBar ?? ""}>
        {LEVELS.map((level) => (
          <button
            key={level}
            className={`${styles.levelBtn ?? ""} ${styles[`level${level}`] ?? ""} ${levelFilter.has(level) ? (styles.levelBtnActive ?? "") : ""}`}
            onClick={() => toggleLevel(level)}
          >
            {level}
          </button>
        ))}
        <span style={{ fontSize: "0.65rem", color: "var(--text-faint)", fontFamily: "var(--font-mono)" }}>
          DEBUG=节点详情 ▶=可展开
        </span>
        <input
          type="text"
          placeholder="过滤来源…"
          className={styles.sourceInput ?? ""}
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          aria-label="按来源过滤"
        />
        <label className={styles.autoScrollLabel ?? ""}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          自动滚动
        </label>
        <button className={styles.clearBtn ?? ""} onClick={handleClear}>
          清空
        </button>
      </div>

      {/* Virtual list */}
      {filtered.length === 0 ? (
        <div className={styles.emptyState ?? ""}>
          {status === "connecting" || status === "reconnecting"
            ? "等待日志流…"
            : "暂无日志"}
        </div>
      ) : (
        <div className={styles.listWrap ?? ""}>
          <List
            listRef={listRef}
            rowCount={filtered.length}
            rowHeight={expandedSet.size > 0 ? getRowHeight : ROW_HEIGHT}
            rowProps={rowProps}
            rowComponent={LogRow}
            overscanCount={8}
            style={{ width: "100%", height }}
          />
        </div>
      )}
    </div>
  )
}
