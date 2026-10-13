"use client"

import { DocRenderer } from "@/components/docs/DocRenderer"
import styles from "./SentinelAssistantPanel.module.css"

interface SentinelAssistantPanelProps {
  title: string
  assistantHtml: string
  assistantMarkdown: string
  renderError: string | null
  isBusy: boolean
  emptyState: string
}

export function SentinelAssistantPanel({
  title,
  assistantHtml,
  assistantMarkdown,
  renderError,
  isBusy,
  emptyState,
}: SentinelAssistantPanelProps) {
  const hasMessage = Boolean(assistantHtml || assistantMarkdown.trim() || renderError)

  return (
    <section className={styles.panel} aria-label={title}>
      <div className={styles.header}>
        <h2 className={styles.title}>{title}</h2>
        <span className={styles.status}>{isBusy ? "采集中" : "等待触发"}</span>
      </div>

      <div className={styles.body}>
        {hasMessage ? (
          <>
            {isBusy && (
              <p className={styles.note}>当前保留最近一次 OpenClaw 回复，新的任务结果返回后会自动覆盖。</p>
            )}
            <div className={styles.message}>
              {assistantHtml ? (
                <DocRenderer html={assistantHtml} />
              ) : renderError ? (
                <>
                  <p className={styles.error}>Markdown 渲染失败：{renderError}</p>
                  {assistantMarkdown.trim() ? (
                    <pre className={styles.fallback}>{assistantMarkdown}</pre>
                  ) : null}
                </>
              ) : (
                <pre className={styles.fallback}>{assistantMarkdown}</pre>
              )}
            </div>
          </>
        ) : (
          <div className={styles.emptyState}>
            <p>{isBusy ? "已触发 Sentinel 任务，等待 OpenClaw 返回消息。" : emptyState}</p>
          </div>
        )}
      </div>
    </section>
  )
}
