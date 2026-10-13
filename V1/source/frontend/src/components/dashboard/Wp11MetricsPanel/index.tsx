"use client"

import { MetricsPanel } from "@/components/dashboard/MetricsPanel"
import { useStats } from "@/lib/hooks/useStats"
import type { WpMeta } from "@/lib/wp-registry"

interface Wp11MetricsPanelProps {
  wp: WpMeta
}

export function Wp11MetricsPanel({ wp }: Wp11MetricsPanelProps) {
  const { stats } = useStats()

  return (
    <MetricsPanel
      wp={wp}
      title="指标趋势"
      valueOverrides={
        stats
          ? {
              attack_pool_size: stats.attack_entry_count,
            }
          : undefined
      }
    />
  )
}
