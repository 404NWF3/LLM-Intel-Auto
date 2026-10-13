"use client"

import { LogViewer } from "@/components/dashboard/LogViewer"
import { Wp12ControlPanel } from "@/components/dashboard/Wp12ControlPanel"
import { Wp12PlanPanel } from "@/components/dashboard/Wp12PlanPanel"
import { Wp12ResultPanel } from "@/components/dashboard/Wp12ResultPanel"
import { useWp12RunController } from "@/lib/hooks/useWp12RunController"
import styles from "./Wp12DashboardContent.module.css"

interface Wp12DashboardContentProps {
  wpId: string
}

export function Wp12DashboardContent({ wpId }: Wp12DashboardContentProps) {
  const controller = useWp12RunController()

  return (
    <div className={styles.body}>
      <div className={styles.workspace}>
        <div className={styles.left}>
          <Wp12ControlPanel controller={controller} />
        </div>

        <div className={styles.right}>
          <Wp12PlanPanel
            result={controller.result}
            planHtml={controller.planHtml}
            planRenderError={controller.planRenderError}
            isBusy={controller.isBusy}
          />
          <Wp12ResultPanel result={controller.result} />
        </div>
      </div>

      <LogViewer streamUrl={`/api/${wpId}/logs/stream`} height={360} />
    </div>
  )
}
