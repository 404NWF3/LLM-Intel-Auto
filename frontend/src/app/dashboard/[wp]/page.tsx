import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { AlertPanel } from "@/components/dashboard/AlertPanel"
import { IntelDashboard } from "@/components/dashboard/IntelDashboard"
import { ResearcherDashboard } from "@/components/dashboard/ResearcherDashboard"
import { LogViewer } from "@/components/dashboard/LogViewer"
import { MetricsPanel } from "@/components/dashboard/MetricsPanel"
import { Wp12DashboardContent } from "@/components/dashboard/Wp12DashboardContent"
import { SandboxDashboard } from "@/components/dashboard/SandboxDashboard"
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

export default async function WpDetailPage({ params }: { params: Promise<Params> }) {
  const { wp: wpId } = await params
  const wp = findWp(wpId)

  if (!wp) notFound()

  if (wp.id === "wp11") {
    return <IntelDashboard />
  }

  if (wp.id === "wp12") {
    return <Wp12DashboardContent />
  }

  if (wp.id === "wp13") {
    return <SandboxDashboard />
  }

  if (wp.id === "wp14") {
    return <ResearcherDashboard />
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
