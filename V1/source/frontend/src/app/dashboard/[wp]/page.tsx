import type { Metadata } from "next"
import { AlertPanel } from "@/components/dashboard/AlertPanel"
import { DebugControlPanel } from "@/components/dashboard/DebugControlPanel"
import { LogViewer } from "@/components/dashboard/LogViewer"
import { MetricsPanel } from "@/components/dashboard/MetricsPanel"
import { SentinelDashboardContent } from "@/components/dashboard/SentinelDashboardContent"
import { Wp11MetricsPanel } from "@/components/dashboard/Wp11MetricsPanel"
import { Wp12DashboardContent } from "@/components/dashboard/Wp12DashboardContent"
import { WpDetailHeader } from "@/components/dashboard/WpDetailHeader"
import { findWp, SORTED_WP_REGISTRY } from "@/lib/wp-registry"
import styles from "./page.module.css"

interface Params {
  wp: string
}

export function generateStaticParams() {
  return SORTED_WP_REGISTRY.map((wp) => ({ wp: wp.id }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>
}): Promise<Metadata> {
  const { wp: wpId } = await params
  const wp = findWp(wpId)

  return {
    title: wp ? `${wp.code} ${wp.label} | 运维控制台` : "WP 详情",
  }
}

export default async function WpDetailPage({
  params,
}: {
  params: Promise<Params>
}) {
  const { wp: wpId } = await params
  const wp = findWp(wpId)

  if (!wp) {
    return (
      <div className={styles.notFound}>
        <p className={styles.notFoundTitle}>智能体 &quot;{wpId}&quot; 未找到</p>
        <p>请检查 URL 或返回控制台入口</p>
      </div>
    )
  }

  if (wp.id === "wp11") {
    return (
      <div className={styles.page}>
        <WpDetailHeader wp={wp} />

        <div className={styles.body}>
          <Wp11MetricsPanel wp={wp} />

          <div className={styles.wp11Layout}>
            <div className={styles.wp11Log}>
              <LogViewer streamUrl={wp.logStream} height={720} />
            </div>
            <div className={styles.wp11Side}>
              <DebugControlPanel />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (wp.id === "sentinel") {
    return (
      <div className={styles.page}>
        <WpDetailHeader wp={wp} />
        <SentinelDashboardContent wpId={wp.id} />
      </div>
    )
  }

  if (wp.id === "wp12") {
    return (
      <div className={styles.page}>
        <WpDetailHeader wp={wp} />
        <Wp12DashboardContent wpId={wp.id} />
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <WpDetailHeader wp={wp} />

      <div className={styles.body}>
        <MetricsPanel wp={wp} />
        <LogViewer streamUrl={wp.logStream} height={320} />

        <div className={styles.twoCol}>
          <AlertPanel wpId={wp.id} title="WP 告警" />
        </div>
      </div>
    </div>
  )
}
