"use client"

import Link from "next/link"
import { Fragment } from "react"
import { usePathname } from "next/navigation"
import { SORTED_WP_REGISTRY } from "@/lib/wp-registry"
import { StatusDot } from "@/components/ui/StatusDot"
import { useSandboxOverview } from "@/lib/api/sandbox"
import { useIntelOverview } from "@/lib/api/intel"
import { useResearcherOverview } from "@/lib/api/researcher"
import { usePentestOverview } from "@/lib/api/pentest"
import { MockModeToggle } from "./MockModeToggle"
import styles from "./DashboardSidebar.module.css"

function WpNavItem({ wpId, code, label }: { wpId: string; code: string; label: string }) {
  const pathname = usePathname()
  const isActive = pathname === `/dashboard/${wpId}`
  const status = "pending"

  return (
    <Link
      href={`/dashboard/${wpId}`}
      className={`${styles.item} ${isActive ? styles.itemActive : ""}`}
    >
      {wpId === "wp11" ? (
        <IntelStatus />
      ) : wpId === "wp12" ? (
        <PentestStatus />
      ) : wpId === "wp13" || wpId === "graphrag" ? (
        <SandboxStatus graph={wpId === "graphrag"} />
      ) : wpId === "wp14" ? (
        <ResearcherStatus />
      ) : (
        <StatusDot status={status} size="sm" />
      )}
      <span>{label}</span>
      <span className={styles.itemCode}>{code}</span>
    </Link>
  )
}

function IntelStatus() {
  const { data, error } = useIntelOverview()
  return (
    <StatusDot
      status={error ? "error" : data?.active ? "running" : data ? "idle" : "pending"}
      size="sm"
    />
  )
}

function SandboxStatus({ graph }: { graph: boolean }) {
  const { data, error } = useSandboxOverview()
  const active =
    data?.active_run_id &&
    (graph ? data.active_run_kind === "graph" : data.active_run_kind !== "graph")
  return (
    <StatusDot
      status={error ? "error" : active ? "running" : data ? "idle" : "pending"}
      size="sm"
    />
  )
}

function ResearcherStatus() {
  const { data, error } = useResearcherOverview()
  return (
    <StatusDot
      status={error ? "error" : data?.active ? "running" : data ? "idle" : "pending"}
      size="sm"
    />
  )
}

function PentestStatus() {
  const { data, error } = usePentestOverview()
  return (
    <StatusDot
      status={error ? "error" : data?.active ? "running" : data ? "idle" : "pending"}
      size="sm"
    />
  )
}

export function DashboardSidebar() {
  const pathname = usePathname()
  return (
    <nav className={styles.nav} aria-label="Dashboard 导航">
      <div className={styles.logo}>
        <div className={styles.logoText}>SAADS</div>
        <div className={styles.logoSub}>运维控制台</div>
      </div>

      <div className={styles.sectionLabel}>工作台</div>

      {SORTED_WP_REGISTRY.map((wp) => (
        <Fragment key={wp.id}>
          <WpNavItem wpId={wp.id} code={wp.code} label={wp.label} />
          {wp.id === "wp11" && (
            <WpNavItem wpId="graphrag" code="KG" label="GraphRAG 知识图谱" />
          )}
        </Fragment>
      ))}

      {![
        "/dashboard/wp11",
        "/dashboard/wp12",
        "/dashboard/wp13",
        "/dashboard/wp14",
        "/dashboard/graphrag",
      ].includes(pathname) && <MockModeToggle />}

      <div className={styles.footer}>
        <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
          ← 返回首页
        </Link>
      </div>
    </nav>
  )
}
