"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { SORTED_WP_REGISTRY } from "@/lib/wp-registry"
import { StatusDot } from "@/components/ui/StatusDot"
import { useWpStatus } from "@/lib/hooks/useWpStatus"
import { MockModeToggle } from "./MockModeToggle"
import styles from "./DashboardSidebar.module.css"

function WpNavItem({ wpId, code, label }: { wpId: string; code: string; label: string }) {
  const pathname = usePathname()
  const isActive = pathname === `/dashboard/${wpId}`
  const { data } = useWpStatus(wpId)
  const status = data?.status ?? "pending"

  return (
    <Link href={`/dashboard/${wpId}`} className={`${styles.item} ${isActive ? styles.itemActive : ""}`}>
      <StatusDot status={status} size="sm" />
      <span>{label}</span>
      <span className={styles.itemCode}>{code}</span>
    </Link>
  )
}

export function DashboardSidebar() {
  return (
    <nav className={styles.nav} aria-label="Dashboard 导航">
      <div className={styles.logo}>
        <div className={styles.logoText}>SAADS</div>
        <div className={styles.logoSub}>运维控制台</div>
      </div>

      <div className={styles.sectionLabel}>智能体</div>

      {SORTED_WP_REGISTRY.map((wp) => (
        <WpNavItem key={wp.id} wpId={wp.id} code={wp.code} label={wp.label} />
      ))}

      <MockModeToggle />

      <div className={styles.footer}>
        <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
          ← 返回首页
        </Link>
      </div>
    </nav>
  )
}
