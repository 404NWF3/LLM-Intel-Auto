"use client"

import { useWpMetrics } from "@/lib/hooks/useWpMetrics"
import type { WpMeta } from "@/lib/wp-registry"
import { SparkLine } from "./SparkLine"
import styles from "./MetricsPanel.module.css"

interface MetricsPanelProps {
  wp: WpMeta
  title?: string
  valueOverrides?: Partial<Record<string, number>>
}

export function MetricsPanel({
  wp,
  title = "指标趋势（过去 48h）",
  valueOverrides,
}: MetricsPanelProps) {
  const keys = wp.metrics.map((metric) => metric.key)
  const { series, isLoading } = useWpMetrics(wp.id, keys)

  const seriesMap = Object.fromEntries(series.map((item) => [item.key, item]))

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>{title}</h2>
      </div>

      <div className={styles.grid}>
        {wp.metrics.map((metric) => {
          const metricSeries = seriesMap[metric.key]
          const values = metricSeries?.points.map((point) => point.value) ?? []
          const latest = values[values.length - 1]
          const displayValue = valueOverrides?.[metric.key] ?? latest

          return (
            <div key={metric.key} className={styles.metricCard}>
              <div className={styles.metricLabel}>{metric.label}</div>
              <div className={styles.metricValue}>
                {displayValue === undefined
                  ? "--"
                  : metric.format === "percent"
                    ? displayValue.toFixed(1)
                    : displayValue.toLocaleString()}
                {displayValue !== undefined && metric.unit && (
                  <span className={styles.metricUnit}>{metric.unit}</span>
                )}
              </div>
              <div className={styles.sparkContainer}>
                {!isLoading && values.length >= 2 && (
                  <SparkLine values={values} height={40} />
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
