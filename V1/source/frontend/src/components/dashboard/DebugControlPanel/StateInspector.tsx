"use client"

import { useWp11State } from "@/lib/hooks/useWp11State"
import styles from "./DebugControlPanel.module.css"

export function StateInspector({ runId }: { runId?: string }) {
  const { snapshot, isLoading } = useWp11State(runId)

  if (isLoading) {
    return (
      <div className={styles.stateSection}>
        <div style={{ padding: "1rem", fontSize: "0.8rem", color: "var(--text-faint)" }}>
          加载状态快照…
        </div>
      </div>
    )
  }

  if (!snapshot) {
    return (
      <div className={styles.stateSection}>
        <div style={{ padding: "1rem", fontSize: "0.8rem", color: "var(--text-faint)" }}>
          暂无运行状态
        </div>
      </div>
    )
  }

  const counters = [
    { label: "已处理", value: snapshot.processed_count, isError: false },
    { label: "新情报", value: snapshot.new_attack_count, isError: false },
    { label: "BOM 待审", value: snapshot.bom_queue_count, isError: false },
    { label: "错误", value: snapshot.errors_count, isError: snapshot.errors_count > 0 },
  ]

  const summaryJson = {
    run_id: snapshot.run_id,
    run_mode: snapshot.run_mode,
    run_status: snapshot.run_status,
    current_node: snapshot.current_node,
    raw_items_count: snapshot.raw_items_count,
    standardized_items_count: snapshot.standardized_items_count,
    dedup_merged_count: snapshot.dedup_merged_count,
    reflection_round: snapshot.reflection_round,
    gap_fill_round: snapshot.gap_fill_round,
    reflection_needed: snapshot.reflection_needed,
    gap_fill_needed: snapshot.gap_fill_needed,
    completed_nodes: snapshot.completed_nodes,
    started_at: snapshot.started_at,
    finished_at: snapshot.finished_at,
  }

  return (
    <div className={styles.stateSection}>
      {/* Counter summary row — visible without expanding */}
      <div className={styles.stateSummaryGrid}>
        {counters.map((c) => (
          <div
            key={c.label}
            className={`${styles.statMetric} ${c.isError ? styles.statMetricError : ""}`}
          >
            <div className={styles.statMetricLabel}>{c.label}</div>
            <div className={styles.statMetricValue}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Expandable JSON */}
      <details className={styles.stateDetails}>
        <summary className={styles.stateSummaryToggle}>
          ▶ 展开完整状态快照
        </summary>
        <pre className={styles.stateJson}>
          {JSON.stringify(
            snapshot._full_state ?? summaryJson,
            null,
            2
          )}
        </pre>
      </details>
    </div>
  )
}
