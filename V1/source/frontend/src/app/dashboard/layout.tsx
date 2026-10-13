import type { Metadata } from "next"
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar"
import styles from "./layout.module.css"

export const metadata: Metadata = {
  title: "运维控制台",
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <DashboardSidebar />
      </aside>
      <div className={styles.main}>
        {children}
      </div>
    </div>
  )
}
