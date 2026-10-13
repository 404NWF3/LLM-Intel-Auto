"use client"

import { AlertPanel } from "@/components/dashboard/AlertPanel"
import { SentinelAssistantPanel } from "@/components/dashboard/SentinelAssistantPanel"
import { SentinelControlPanel } from "@/components/dashboard/SentinelControlPanel"
import { useSentinelRunController } from "@/lib/hooks/useSentinelRunController"
import styles from "./SentinelDashboardContent.module.css"

interface SentinelDashboardContentProps {
  wpId: string
}

export function SentinelDashboardContent({ wpId }: SentinelDashboardContentProps) {
  const controller = useSentinelRunController()

  return (
    <div className={styles.body}>
      <SentinelAssistantPanel
        title="OpenClaw 智能体回复"
        assistantHtml={controller.assistantHtml}
        assistantMarkdown={controller.assistantMarkdown}
        renderError={controller.assistantRenderError}
        isBusy={controller.isBusy}
        emptyState="暂未收到 OpenClaw 消息。触发一次 Sentinel 采集后，回复会显示在这里，并保留到你点击重置。"
      />

      <div className={styles.twoCol}>
        <AlertPanel wpId={wpId} title="WP 告警" />
        <SentinelControlPanel controller={controller} />
      </div>
    </div>
  )
}
