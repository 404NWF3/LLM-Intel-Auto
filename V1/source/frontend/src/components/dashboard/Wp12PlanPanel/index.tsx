"use client"

import { DocRenderer } from "@/components/docs/DocRenderer"
import type { Wp12RunResult } from "@/lib/types/wp12"
import styles from "./Wp12PlanPanel.module.css"

interface Wp12PlanPanelProps {
  result: Wp12RunResult | null
  planHtml: string
  planRenderError: string | null
  isBusy: boolean
}

function resolveBadge(result: Wp12RunResult | null): { label: string; tone: string } | null {
  if (!result) return null
  const valid = result.package_validation?.valid
  if (valid === false) return { label: "验证未通过", tone: styles.badgeWarn ?? "" }
  if (result.verdict === "triaged") return { label: "Triage", tone: styles.badgeMuted ?? "" }
  if (result.verdict === "planned") return { label: "Planned", tone: styles.badgeGood ?? "" }
  if (result.verdict === "invalid") return { label: "Invalid", tone: styles.badgeWarn ?? "" }
  return null
}

export function Wp12PlanPanel({
  result,
  planHtml,
  planRenderError,
  isBusy,
}: Wp12PlanPanelProps) {
  const badge = resolveBadge(result)
  const hasPlan = Boolean(planHtml || result?.plan_markdown.trim() || planRenderError)

  return (
    <section className={styles.panel} aria-label="WP1-2 测试方案">
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>测试方案</h2>
          <p className={styles.subtitle}>`plan_markdown` 作为主阅读对象，结构化结果只作辅助说明。</p>
        </div>
        {badge ? <span className={`${styles.badge} ${badge.tone}`}>{badge.label}</span> : null}
      </div>

      {result ? (
        <div className={styles.meta}>
          <span>{result.summary.canonical_name ? String(result.summary.canonical_name) : result.attack_id}</span>
          <span>{result.package_kind || "unknown-package"}</span>
          <span>{result.generation_mode || "unknown-mode"}</span>
        </div>
      ) : null}

      <div className={styles.body}>
        {hasPlan ? (
          <>
            {isBusy ? (
              <p className={styles.note}>当前保留最近一次可用结果，新的运行完成后会自动覆盖。</p>
            ) : null}

            {planHtml ? (
              <DocRenderer html={planHtml} />
            ) : planRenderError ? (
              <>
                <p className={styles.error}>Markdown 渲染失败：{planRenderError}</p>
                {result?.plan_markdown ? (
                  <pre className={styles.fallback}>{result.plan_markdown}</pre>
                ) : null}
              </>
            ) : (
              <pre className={styles.fallback}>{result?.plan_markdown ?? ""}</pre>
            )}
          </>
        ) : (
          <div className={styles.emptyState}>
            选择攻击样本并启动运行后，这里会显示完整的测试方案 Markdown。
          </div>
        )}
      </div>
    </section>
  )
}
