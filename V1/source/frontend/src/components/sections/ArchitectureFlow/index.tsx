import { Fragment } from "react"
import { SORTED_WP_REGISTRY } from "@/lib/wp-registry"
import type { WpMeta } from "@/lib/wp-registry"
import { ScrollReveal } from "@/components/ui/ScrollReveal"
import styles from "./ArchitectureFlow.module.css"

/* ── Per-card UI data (tags + expandable metrics) ─────────────────────────── */
interface WpExtra {
  tags: [string, string, string]
  metrics: [
    { label: string; value: string },
    { label: string; value: string },
    { label: string; value: string },
  ]
}

const WP_EXTRA: Record<string, WpExtra> = {
  wp11: {
    tags: ["情报报告", "AI BOM", "CVE 标注"],
    metrics: [
      { label: "已入库情报", value: "2,400+" },
      { label: "OWASP 覆盖率", value: "100%" },
      { label: "今日新增", value: "12 条" },
    ],
  },
  wp12: {
    tags: ["测试方案", "执行脚本", "OWASP 映射"],
    metrics: [
      { label: "生成脚本", value: "380+" },
      { label: "覆盖威胁类别", value: "10/10" },
      { label: "今日生成", value: "8 个" },
    ],
  },
  wp13: {
    tags: ["沙盒环境", "异常数据集", "漏洞验证"],
    metrics: [
      { label: "沙盒会话", value: "64" },
      { label: "采集数据集", value: "128" },
      { label: "已验证漏洞", value: "37" },
    ],
  },
  wp14: {
    tags: ["检测模型", "评估报告", "防御建议"],
    metrics: [
      { label: "已训练模型", value: "12" },
      { label: "最优 F1", value: "97.3%" },
      { label: "迭代轮次", value: "240" },
    ],
  },
}

/* ── WP Card component ────────────────────────────────────────────────────── */
function WpCard({ wp }: { wp: WpMeta }) {
  const extra = WP_EXTRA[wp.id]
  const isGeneric = wp.layer === "generic"

  return (
    <div
      className={`${styles.wpCard} ${isGeneric ? styles.wpCardGeneric : ""}`}
    >
      <div className={styles.cardCode}>{wp.code}</div>
      <div className={styles.cardRole}>{wp.label}</div>
      <p className={styles.cardDesc}>{wp.description}</p>

      {extra && (
        <div className={styles.tagRow}>
          {extra.tags.map((tag) => (
            <span key={tag} className={styles.tag}>
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Expandable on hover */}
      {extra && (
        <div className={styles.cardExpand}>
          <div className={styles.expandInner}>
            <div className={styles.expandTitle}>核心产出</div>
            {extra.metrics.map((m) => (
              <div key={m.label} className={styles.expandRow}>
                <span>{m.label}</span>
                <span className={styles.expandVal}>{m.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Arrow connector between cards ───────────────────────────────────────── */
function ConnectorArrow({ isBoundary = false }: { isBoundary?: boolean }) {
  return (
    <div
      className={`${styles.connector} ${isBoundary ? styles.connectorBoundary : ""}`}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 48 36"
        className={styles.connectorSvg}
        xmlns="http://www.w3.org/2000/svg"
      >
        <line
          x1="4"
          y1="18"
          x2="38"
          y2="18"
          stroke="rgba(160,106,67,0.4)"
          strokeWidth="1.5"
          strokeDasharray="5 4"
          className={styles.connectorLine}
        />
        {/* Inline arrowhead polygon — no marker ID needed */}
        <polygon points="36,13 44,18 36,23" fill="rgba(160,106,67,0.5)" />
      </svg>
    </div>
  )
}

/* ── ArchitectureFlow section ─────────────────────────────────────────────── */
export function ArchitectureFlow() {
  const homepageFlow = SORTED_WP_REGISTRY.filter((wp) => wp.id !== "sentinel")

  return (
    <section className="section" id="architecture">
      <div className="container">
        {/* Header */}
        <ScrollReveal className={styles.header}>
          <span className="eyebrow">攻防架构</span>
          <h2 className={styles.sectionTitle}>全链路安全闭环</h2>
        </ScrollReveal>

        {/* Layer label bar — hidden on < 1120px */}
        <div className={styles.layerBar} aria-hidden="true">
          <div className={styles.layerLabelGeneric}>
            <span className={`${styles.layerDot} ${styles.layerDotGeneric}`} />
            通用层 — 情报与方案
          </div>
          <div className={styles.layerLabelUser}>
            <span className={`${styles.layerDot} ${styles.layerDotUser}`} />
            用户层 — 模拟与检测
          </div>
        </div>

        {/* Pipeline */}
        <div className={styles.pipeline}>
          {homepageFlow.map((wp, i) => (
            <Fragment key={wp.id}>
              <ScrollReveal delay={i as 0 | 1 | 2 | 3}>
                <WpCard wp={wp} />
              </ScrollReveal>
              {i < 3 && <ConnectorArrow isBoundary={i === 1} />}
            </Fragment>
          ))}
        </div>

        {/* Feedback loop indicator */}
        <ScrollReveal>
          <div className={styles.feedbackRow} aria-label="攻防闭环反馈">
            <div className={styles.feedbackLine} />
            <span className={styles.feedbackLabel}>↺ 攻防闭环</span>
            <div className={styles.feedbackLine} />
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
