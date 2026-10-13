"use client"

import type { Wp12RunController } from "@/lib/hooks/useWp12RunController"
import styles from "./Wp12ControlPanel.module.css"

const STATUS_LABELS: Record<string, string> = {
  queued: "已排队",
  running: "运行中",
  cancelling: "取消中",
  succeeded: "已完成",
  failed: "已失败",
  cancelled: "已取消",
}

interface Wp12ControlPanelProps {
  controller: Wp12RunController
}

export function Wp12ControlPanel({ controller }: Wp12ControlPanelProps) {
  const {
    feedQuery,
    setFeedQuery,
    feedItems,
    isLoadingFeed,
    feedError,
    selectedAttackId,
    setSelectedAttackId,
    selectedFeedDetail,
    isLoadingFeedDetail,
    feedDetailError,
    runStatus,
    runError,
    start,
    cancel,
    clearResult,
    isBusy,
    isStarting,
  } = controller

  return (
    <section className={styles.panel} aria-label="WP1-2 控制台">
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>样本选择与运行控制</h2>
          <p className={styles.subtitle}>从现有 WP1-2 feed 中选择一条攻击样本，手动生成测试方案。</p>
        </div>
        {runStatus?.run_id ? <span className={styles.runId}>{runStatus.run_id}</span> : null}
      </div>

      <div className={styles.section}>
        <label className={styles.label} htmlFor="wp12-search">
          搜索攻击样本
        </label>
        <input
          id="wp12-search"
          className={styles.search}
          type="text"
          value={feedQuery}
          onChange={(event) => setFeedQuery(event.target.value)}
          placeholder="按 attack code、名称或摘要过滤"
        />
        {feedError ? <p className={styles.errorText}>{feedError}</p> : null}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span className={styles.label}>候选样本</span>
          <span className={styles.metaText}>{isLoadingFeed ? "加载中" : `${feedItems.length} 条`}</span>
        </div>
        <div className={styles.feedList}>
          {feedItems.map((item) => {
            const active = item.attack_id === selectedAttackId
            return (
              <button
                key={item.attack_id}
                type="button"
                className={`${styles.feedItem} ${active ? styles.feedItemActive : ""}`}
                onClick={() => setSelectedAttackId(item.attack_id)}
              >
                <div className={styles.feedTop}>
                  <span className={styles.feedCode}>{item.attack_code}</span>
                  <span className={styles.feedScore}>{item.primary_cvss_base_score.toFixed(1)}</span>
                </div>
                <div className={styles.feedName}>{item.canonical_name}</div>
                <div className={styles.feedMeta}>
                  <span>{item.attack_family || "unknown"}</span>
                  <span>{item.taxonomy_code || "no-taxonomy"}</span>
                </div>
                <p className={styles.feedSummary}>{item.summary}</p>
              </button>
            )
          })}

          {!isLoadingFeed && feedItems.length === 0 ? (
            <div className={styles.emptyState}>没有匹配的攻击样本。</div>
          ) : null}
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span className={styles.label}>样本摘要</span>
          {isLoadingFeedDetail ? <span className={styles.metaText}>读取中</span> : null}
        </div>

        {feedDetailError ? <p className={styles.errorText}>{feedDetailError}</p> : null}

        {selectedFeedDetail ? (
          <div className={styles.detailCard}>
            <div className={styles.detailGrid}>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>攻击族</span>
                <span className={styles.detailValue}>{selectedFeedDetail.attack_family || "unknown"}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Taxonomy</span>
                <span className={styles.detailValue}>
                  {selectedFeedDetail.taxonomy_code || "N/A"} {selectedFeedDetail.taxonomy_name || ""}
                </span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>组件</span>
                <span className={styles.detailValue}>{selectedFeedDetail.component_name || "N/A"}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>资产</span>
                <span className={styles.detailValue}>{selectedFeedDetail.asset_name || "N/A"}</span>
              </div>
            </div>
            <p className={styles.summaryText}>{selectedFeedDetail.summary}</p>
            {selectedFeedDetail.description ? (
              <p className={styles.detailText}>{selectedFeedDetail.description}</p>
            ) : null}
            {selectedFeedDetail.artifact_uri ? (
              <p className={styles.detailText}>
                <strong>Artifact:</strong> {selectedFeedDetail.artifact_uri}
              </p>
            ) : null}
          </div>
        ) : (
          <div className={styles.emptyState}>选择一条攻击样本后，这里会显示样本摘要。</div>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span className={styles.label}>运行状态</span>
          {runStatus ? (
            <span className={styles.statusPill}>{STATUS_LABELS[runStatus.status] ?? runStatus.status}</span>
          ) : null}
        </div>

        {runStatus ? (
          <div className={styles.progressBlock}>
            <div className={styles.progressMeta}>
              <span>{runStatus.current_task || "等待启动"}</span>
              <span>{runStatus.percent}%</span>
            </div>
            <div className={styles.progressBar}>
              <span className={styles.progressFill} style={{ width: `${runStatus.percent}%` }} />
            </div>
          </div>
        ) : (
          <p className={styles.detailText}>当前没有活动运行。</p>
        )}

        {runError ? <p className={styles.errorText}>{runError}</p> : null}
      </div>

      <div className={styles.footer}>
        {isBusy ? (
          <button className={styles.cancelBtn} type="button" onClick={() => void cancel()}>
            取消运行
          </button>
        ) : (
          <button
            className={styles.startBtn}
            type="button"
            disabled={!selectedAttackId || isStarting}
            onClick={() => void start()}
          >
            {isStarting ? "启动中" : "生成测试方案"}
          </button>
        )}

        <button className={styles.secondaryBtn} type="button" onClick={clearResult}>
          清空当前结果
        </button>
      </div>
    </section>
  )
}
