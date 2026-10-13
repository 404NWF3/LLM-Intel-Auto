"use client"

import { useState } from "react"
import type { ReactNode } from "react"
import type { WpRunRequest, WpRunStatus, RunMode } from "@/lib/types/dashboard"
import { RUN_MODE_LABELS } from "@/lib/types/dashboard"
import styles from "./DebugControlPanel.module.css"

interface RunControlProps {
  activeRun: WpRunStatus | undefined
  isStarting: boolean
  isCancelling: boolean
  onStart: (req: WpRunRequest) => Promise<void>
  onCancel: (runId: string) => Promise<void>
  /** 渲染在 runCard 内部（用于插入 RunProgressTracker）*/
  children?: ReactNode
}

const RUN_MODES: RunMode[] = [
  "bootstrap",
  "incremental",
  "gap_fill",
  "weak_signal_focus",
  "mixed",
]

export function RunControl({
  activeRun,
  isStarting,
  isCancelling,
  onStart,
  onCancel,
  children,
}: RunControlProps) {
  const [mode, setMode] = useState<RunMode>("bootstrap")

  const isRunning =
    activeRun?.status === "running" || activeRun?.status === "queued"

  const handleStart = async () => {
    await onStart({ run_mode: mode })
  }

  const handleCancel = async () => {
    if (activeRun) await onCancel(activeRun.run_id)
  }

  return (
    <div className={styles.runCard}>
      <div className={styles.runCardHeader}>
        <h2 className={styles.runCardTitle}>运行控制</h2>
        {activeRun && (
          <span style={{ fontSize: "0.72rem", fontFamily: "var(--font-mono)", color: "var(--text-faint)" }}>
            {activeRun.run_id}
          </span>
        )}
      </div>

      <div className={styles.runCardBody}>
        <select
          className={styles.modeSelect}
          value={mode}
          onChange={(e) => setMode(e.target.value as RunMode)}
          disabled={isRunning}
          aria-label="选择运行模式"
        >
          {RUN_MODES.map((m) => (
            <option key={m} value={m}>
              {RUN_MODE_LABELS[m]}
            </option>
          ))}
        </select>

        {!isRunning ? (
          <button
            className={styles.runBtn}
            onClick={handleStart}
            disabled={isStarting}
          >
            {isStarting ? "启动中…" : "启动运行"}
          </button>
        ) : (
          <button
            className={styles.cancelBtn}
            onClick={handleCancel}
            disabled={isCancelling}
          >
            {isCancelling ? "取消中…" : "取消运行"}
          </button>
        )}
      </div>
      {children}
    </div>
  )
}
