"use client"

import { ScrollReveal } from "@/components/ui/ScrollReveal"
import { CountUp } from "@/components/ui/CountUp"
import { useStats } from "@/lib/hooks/useStats"
import type { StatsResponse } from "@/lib/types/stats"
import styles from "./KpiStrip.module.css"

const formatCount = (n: number) => Math.round(n).toLocaleString("zh-CN")
const formatPercent = (n: number) => n.toFixed(1)

function buildKpis(stats: StatsResponse | undefined) {
  return [
    {
      value: stats?.item_count,
      suffix: "条",
      label: "已入库安全情报",
      sub: stats
        ? `来自 ${stats.source_count} 个来源 · 去重统计`
        : "漏洞库、研究论文与安全社区",
      formatter: formatCount,
    },
    {
      value: stats?.core_coverage_pct,
      suffix: "%",
      label: "核心安全话题覆盖率",
      sub: stats
        ? `${stats.core_topics_covered} / ${stats.core_topics_total} 类话题已有情报`
        : "按情报库核心话题标注统计",
      formatter: formatPercent,
    },
    {
      value: stats?.script_count,
      suffix: "份",
      label: "已生成测试脚本",
      sub: "WP1-2 已完成且可下载的脚本",
      formatter: formatCount,
    },
  ]
}

export function KpiStrip() {
  const { stats, isLoading, isValidating, error, refresh } = useStats()
  const kpis = buildKpis(stats)
  const status = error
    ? stats
      ? "同步失败，显示上次成功同步的数据。"
      : "统计暂不可用，请检查后端服务。"
    : isLoading
      ? "正在同步情报库…"
      : stats
        ? `更新于 ${new Date(stats.updated_at).toLocaleTimeString("zh-CN", { hour12: false })} · 每 30 秒自动同步`
        : "等待同步"

  return (
    <section
      className={styles.section}
      id="kpi-strip"
      aria-label="关键指标"
      aria-busy={isLoading}
    >
      <div className="container">
        <div className="kpi-strip">
          {kpis.map((kpi, i) => (
            <ScrollReveal key={kpi.label} delay={i as 0 | 1 | 2}>
              <div className="kpi">
                <div className={`kpi__value ${styles.valueRow}`}>
                  {kpi.value === undefined ? (
                    <span aria-label="数据暂不可用">—</span>
                  ) : (
                    <>
                      <CountUp to={kpi.value} formatter={kpi.formatter} duration={1600} />
                      <span className={styles.suffix}>{kpi.suffix}</span>
                    </>
                  )}
                </div>
                <div className="kpi__label">{kpi.label}</div>
                <div className={styles.sub}>{kpi.sub}</div>
              </div>
            </ScrollReveal>
          ))}
        </div>
        <div className={styles.syncRow}>
          <span role="status">{status}</span>
          <button
            type="button"
            onClick={() => void refresh().catch(() => {})}
            disabled={isValidating}
          >
            {isValidating ? "同步中…" : "刷新数据"}
          </button>
        </div>
      </div>
    </section>
  )
}
