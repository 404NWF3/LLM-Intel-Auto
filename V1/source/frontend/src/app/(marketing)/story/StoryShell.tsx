"use client"

import { useRef, useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { ArrowRight, BookOpen } from "lucide-react"
import styles from "./story.module.css"

/* ─────────────────────────────────────────────────────────────────────────────
   Static data constants
   ───────────────────────────────────────────────────────────────────────────── */

const SLIDE_COUNT = 6

const SLIDE_TITLES = [
  "开场",
  "社会价值",
  "设计思想",
  "WP1-1",
  "WP1-2",
  "攻防闭环",
] as const

const OWASP_ITEMS = [
  { id: "LLM01", name: "Prompt Injection", pct: 100 },
  { id: "LLM02", name: "Insecure Output", pct: 100 },
  { id: "LLM03", name: "Training Data Poisoning", pct: 70 },
  { id: "LLM04", name: "Model DoS", pct: 100 },
  { id: "LLM05", name: "Supply Chain", pct: 60 },
  { id: "LLM06", name: "Sensitive Info Disclosure", pct: 100 },
  { id: "LLM07", name: "Insecure Plugin Design", pct: 100 },
  { id: "LLM08", name: "Excessive Agency", pct: 100 },
  { id: "LLM09", name: "Overreliance", pct: 80 },
  { id: "LLM10", name: "Model Theft", pct: 100 },
] as const


const DATA_SOURCES = [
  { name: "NVD / NIST", type: "CVE 数据库", freq: "实时", count: "1,200+", status: "running" },
  { name: "MITRE ATT&CK", type: "攻击框架", freq: "每周", count: "380+", status: "running" },
  {
    name: "OWASP LLM Top 10",
    type: "LLM 威胁分类",
    freq: "季度",
    count: "10 类",
    status: "running",
  },
  {
    name: "GitHub Advisory",
    type: "代码漏洞",
    freq: "实时",
    count: "620+",
    status: "running",
  },
  { name: "暗网监控", type: "零日情报", freq: "实时", count: "—", status: "pending" },
] as const


const THREATS = [
  { code: "LLM01", name: "提示词注入", risk: "critical", riskLabel: "高危" },
  { code: "LLM08", name: "过度代理权限", risk: "critical", riskLabel: "高危" },
  { code: "LLM06", name: "敏感信息泄露", risk: "high", riskLabel: "高危" },
  { code: "LLM04", name: "模型拒绝服务", risk: "high", riskLabel: "中高" },
  { code: "LLM02", name: "不安全输出处理", risk: "high", riskLabel: "高危" },
] as const

const TIMELINE = [
  { label: "WP1-1\n情报采集", date: "已完成", state: "done" },
  { label: "WP1-2\n渗透测试", date: "Q2 2026", state: "active" },
  { label: "WP1-3 / WP1-4\n用户层接入", date: "Q3 2026", state: "future" },
  { label: "多系统\n横向扩展", date: "Q4 2026", state: "future" },
] as const

const WP_PIPELINE = [
  { code: "WP1-1", role: "情报采集" },
  { code: "WP1-2", role: "渗透测试" },
  { code: "WP1-3", role: "沙盒模拟" },
  { code: "WP1-4", role: "异常检测" },
] as const

/* ─────────────────────────────────────────────────────────────────────────────
   Slide wrapper helper
   ───────────────────────────────────────────────────────────────────────────── */

function SlideWrap({
  index,
  className,
  children,
}: {
  index: number
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      data-slide-index={index}
      className={`${styles.slide}${className ? ` ${className}` : ""}`}
      aria-label={`第 ${index + 1} 屏：${SLIDE_TITLES[index] ?? ""}`}
    >
      {children}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Slide 0 — 开场
   ───────────────────────────────────────────────────────────────────────────── */

function Slide0Opening() {
  return (
    <SlideWrap index={0} className={styles.openingBg}>
      <div className={styles.fullLayout}>
        <div className={styles.openingInner}>
          <p className={styles.openingEyebrow}>SUFE · 2026 · AI 系统安全研究</p>

          <h1 className={styles.bigQuote}>
            每个 AI 系统，
            <br />
            都是一个新的攻击面。
          </h1>

          <div className={styles.scrollHint}>
            <span>向下探索</span>
            <span className={styles.scrollArrow} aria-hidden="true">
              ↓
            </span>
          </div>

        </div>
      </div>
    </SlideWrap>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Slide 1 — 社会价值
   ───────────────────────────────────────────────────────────────────────────── */

function Slide1SocialValue() {
  return (
    <SlideWrap index={1}>
      <div className={styles.splitLayout}>
        {/* Left track */}
        <div className={styles.leftTrack}>
          <p className={styles.slideEyebrow}>社会价值线 · 第一章</p>
          <h2 className={styles.slideH2}>
            为什么 AI 安全
            <br />
            如此紧迫？
          </h2>
          <p className={styles.slideLead}>
            随着大模型在金融、医疗、司法等关键领域快速部署，每一个 AI
            系统都成为新的攻击目标。传统安全体系为人类代码设计，无法应对模型特有的威胁。
          </p>
          <div className={styles.factList}>
            <div className={styles.factItem}>
              <div className={styles.factBullet}>▸</div>
              <p className={styles.factText}>
                <span className={styles.factStrong}>提示词注入</span>
                已成为 LLM 应用首要攻击面，OWASP 将其列为 LLM Top 1 威胁
              </p>
            </div>
            <div className={styles.factItem}>
              <div className={styles.factBullet}>▸</div>
              <p className={styles.factText}>
                传统 WAF 与 IDS <span className={styles.factStrong}>无法检测</span>
                针对模型行为的攻击——它们绕过所有基于规则的防御
              </p>
            </div>
            <div className={styles.factItem}>
              <div className={styles.factBullet}>▸</div>
              <p className={styles.factText}>
                <span className={styles.factStrong}>自动化威胁</span>演进速度已超越人工响应能力，
                主动探测与防御势在必行
              </p>
            </div>
          </div>
        </div>

        {/* Right track */}
        <div className={styles.rightTrack}>
          <p className={styles.rightHeader}>核心威胁类别</p>
          <div className={styles.threatGrid}>
            {THREATS.map((t) => (
              <div key={t.code} className={styles.threatCard}>
                <div className={styles.threatCode}>{t.code}</div>
                <div className={styles.threatName}>{t.name}</div>
                <div className={styles.threatRiskRow}>
                  <span
                    className={`${styles.threatRiskDot} ${
                      t.risk === "critical" ? styles.riskCritical : styles.riskHigh
                    }`}
                  />
                  <span className={styles.threatRiskLabel}>{t.riskLabel}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SlideWrap>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Slide 2 — 设计思想
   ───────────────────────────────────────────────────────────────────────────── */

function Slide2Philosophy() {
  return (
    <SlideWrap index={2}>
      <div className={styles.splitLayout}>
        {/* Left track */}
        <div className={styles.leftTrack}>
          <p className={styles.slideEyebrow}>设计思想</p>
          <blockquote className={styles.pullQuote}>
            防御不是终点，
            <br />
            而是自我进化的起点。
          </blockquote>
          <p className={styles.slideLead}>
            SAADS 摒弃被动响应思路，让系统主动探测、自动验证、持续迭代。
            四个智能体形成攻防闭环——情报驱动测试，测试驱动检测，检测反哺情报。
          </p>
          <p className={styles.slideLead} style={{ marginBottom: 0 }}>
            通用层（WP1-1/1-2）持续运行；用户层（WP1-3/1-4）按需接入，实现分层解耦、渐进式演进。
          </p>
        </div>

        {/* Right track */}
        <div className={styles.rightTrack}>
          <p className={styles.rightHeader}>传统安全 vs SAADS</p>
          <div className={styles.compareGrid}>
            {/* Legacy column */}
            <div className={`${styles.compareCol} ${styles.compareColLegacy}`}>
              <p className={`${styles.compareColTitle} ${styles.compareColTitleLegacy}`}>
                传统安全体系
              </p>
              {["事后被动响应", "依赖人工规则", "静态防护策略", "单点孤立防御", "漏洞发现延迟高"].map(
                (row) => (
                  <div key={row} className={styles.compareRow}>
                    <span className={styles.compareBullet} />
                    {row}
                  </div>
                )
              )}
            </div>
            {/* SAADS column */}
            <div className={`${styles.compareCol} ${styles.compareColSaads}`}>
              <p className={`${styles.compareColTitle} ${styles.compareColTitleSaads}`}>
                SAADS 攻防闭环
              </p>
              {["主动探测发现", "智能体自主决策", "持续动态进化", "四智能体协作", "零日情报实时响应"].map(
                (row) => (
                  <div key={row} className={styles.compareRow}>
                    <span className={styles.compareBullet} />
                    {row}
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      </div>
    </SlideWrap>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Slide 3 — WP1-1 情报采集
   ───────────────────────────────────────────────────────────────────────────── */

function Slide3Wp11() {
  return (
    <SlideWrap index={3}>
      <div className={styles.splitLayout}>
        {/* Left track */}
        <div className={styles.leftTrack}>
          <p className={styles.slideEyebrow}>WP1-1 · 通用层 · 情报采集智能体</p>
          <h2 className={styles.slideH2}>
            知己知彼，
            <br />
            百战不殆
          </h2>
          <p className={styles.slideLead}>
            持续监控全球 AI 安全威胁信息源，自动采集、结构化标注、入库，
            构建覆盖 OWASP LLM Top 10 的动态威胁情报库，驱动下游智能体决策。
          </p>
          <div className={styles.flowSteps}>
            {[
              "监控 NVD / MITRE / GitHub 等多源情报",
              "LLM 驱动结构化解析与 AI BOM 标注",
              "入库威胁情报，触发覆盖度分析",
              "向 WP1-2 输出测试驱动情报包",
            ].map((step, i) => (
              <div key={i} className={`${styles.flowStep} ${i === 0 ? styles.flowStepActive : ""}`}>
                <span className={styles.flowStepNum}>{i + 1}</span>
                <span className={styles.flowStepText}>{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right track */}
        <div className={styles.rightTrack}>
          <p className={styles.rightHeader}>情报数据来源</p>
          <div className={styles.tableWrapper}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>来源</th>
                  <th>类型</th>
                  <th>频率</th>
                  <th>条目</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {DATA_SOURCES.map((row) => (
                  <tr key={row.name}>
                    <td className={styles.tdMono}>{row.name}</td>
                    <td>{row.type}</td>
                    <td>{row.freq}</td>
                    <td>{row.count}</td>
                    <td>
                      <span
                        className={`${styles.pillBadge} ${
                          row.status === "running" ? styles.pillRunning : styles.pillPending
                        }`}
                      >
                        {row.status === "running" ? "采集中" : "规划"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </SlideWrap>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Slide 4 — WP1-2 渗透测试
   ───────────────────────────────────────────────────────────────────────────── */

function Slide4Wp12() {
  return (
    <SlideWrap index={4}>
      <div className={styles.splitLayout}>
        {/* Left track */}
        <div className={styles.leftTrack}>
          <p className={styles.slideEyebrow}>WP1-2 · 通用层 · 渗透测试智能体</p>
          <h2 className={styles.slideH2}>
            以攻促防，
            <br />
            自动化红队
          </h2>
          <p className={styles.slideLead}>
            接收 WP1-1 威胁情报，自动生成覆盖 OWASP LLM Top 10 的通用测试方案与可执行脚本。
            不执行攻击，只生成方案——确保用户在授权环境中自主运行。
          </p>
          <div className={styles.flowSteps}>
            {[
              "接收情报包，确定攻击类型与目标能力",
              "生成通用测试 Prompt 与 Payload 模板",
              "封装为带 OWASP 映射的可执行脚本",
              "向 WP1-3 沙盒推送待执行测试队列",
            ].map((step, i) => (
              <div key={i} className={styles.flowStep}>
                <span className={styles.flowStepNum}>{i + 1}</span>
                <span className={styles.flowStepText}>{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right track */}
        <div className={styles.rightTrack}>
          <p className={styles.rightHeader}>OWASP LLM Top 10 覆盖率</p>
          <div className={styles.owaspList}>
            {OWASP_ITEMS.map((item) => (
              <div key={item.id} className={styles.owaspItem}>
                <span className={styles.owaspId}>{item.id}</span>
                <div className={styles.owaspBarWrapper}>
                  <span className={styles.owaspName}>{item.name}</span>
                  <div className={styles.owaspBarTrack}>
                    <div
                      className={`${styles.owaspBarFill} ${
                        item.pct < 100 ? styles.owaspBarPartial : ""
                      }`}
                      style={{ width: `${item.pct}%` }}
                    />
                  </div>
                </div>
                <span
                  className={`${styles.owaspPct} ${
                    item.pct < 100 ? styles.owaspPctPartial : ""
                  }`}
                >
                  {item.pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SlideWrap>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Slide 7 — 攻防闭环（Closing）
   ───────────────────────────────────────────────────────────────────────────── */

function Slide7Closing() {
  return (
    <SlideWrap index={5}>
      <div className={styles.fullLayout}>
        <div className={styles.closingInner}>
          <p className={styles.slideEyebrow} style={{ alignSelf: "center" }}>
            攻防闭环 · 演进路线
          </p>

          <h2 className={styles.closingH2}>
            从情报到防御，
            <br />
            攻防闭环，持续进化
          </h2>

          <p className={styles.closingLead}>
            四个智能体协同运作，情报驱动测试，测试驱动检测，检测反哺情报，
            构建无限循环的自我进化防御体系。
          </p>

          {/* Mini pipeline */}
          <div className={styles.miniPipeline} aria-label="四智能体攻防流水线">
            {WP_PIPELINE.map((wp, i) => (
              <div key={wp.code} style={{ display: "flex", alignItems: "center", flex: 1 }}>
                <div className={styles.pipelineNode} style={{ flex: 1 }}>
                  <div className={styles.pipelineNodeCode}>{wp.code}</div>
                  <div className={styles.pipelineNodeRole}>{wp.role}</div>
                </div>
                {i < WP_PIPELINE.length - 1 && (
                  <div className={styles.pipelineArrow} aria-hidden="true">
                    →
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Evolution timeline */}
          <div
            className={styles.timeline}
            role="list"
            aria-label="项目演进时间轴"
          >
            {TIMELINE.map((item) => (
              <div key={item.label} className={styles.timelineItem} role="listitem">
                <div
                  className={`${styles.timelineDot} ${
                    item.state === "done"
                      ? styles.timelineDotDone
                      : item.state === "active"
                        ? styles.timelineDotActive
                        : ""
                  }`}
                />
                <div className={styles.timelineLabel}>
                  {item.label.split("\n").map((line, i) => (
                    <span key={i}>
                      {i > 0 && <br />}
                      {line}
                    </span>
                  ))}
                </div>
                <div className={styles.timelineDate}>{item.date}</div>
              </div>
            ))}
          </div>

          {/* CTA */}
          <div className={styles.closingActions}>
            <Link href="/dashboard" className="button button--primary">
              进入控制面板
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link href="/docs" className="button button--secondary">
              <BookOpen size={16} aria-hidden="true" />
              查阅技术文档
            </Link>
          </div>
        </div>
      </div>
    </SlideWrap>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   StoryShell — main client shell
   ───────────────────────────────────────────────────────────────────────────── */

export function StoryShell() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [current, setCurrent] = useState(0)
  const isScrolling = useRef(false)

  /* Keyboard navigation */
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return
      }

      if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === "j") {
        e.preventDefault()
        setCurrent((n) => Math.min(n + 1, SLIDE_COUNT - 1))
      }
      if (e.key === "ArrowUp" || e.key === "PageUp" || e.key === "k") {
        e.preventDefault()
        setCurrent((n) => Math.max(n - 1, 0))
      }
      if (e.key === "Home") {
        e.preventDefault()
        setCurrent(0)
      }
      if (e.key === "End") {
        e.preventDefault()
        setCurrent(SLIDE_COUNT - 1)
      }
    }

    window.addEventListener("keydown", handleKey, { passive: false })
    return () => window.removeEventListener("keydown", handleKey)
  }, [])

  /* Scroll to target when current changes from keyboard/dot click */
  useEffect(() => {
    const container = containerRef.current
    if (!container || isScrolling.current) return

    const slide = container.children[current] as HTMLElement | undefined
    if (slide) {
      isScrolling.current = true
      slide.scrollIntoView({ behavior: "smooth", block: "start" })
      setTimeout(() => {
        isScrolling.current = false
      }, 800)
    }
  }, [current])

  /* Track current slide from scroll position */
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !isScrolling.current) {
            const idx = parseInt(
              (entry.target as HTMLElement).dataset["slideIndex"] ?? "0"
            )
            setCurrent(idx)
          }
        })
      },
      { root: container, threshold: 0.55 }
    )

    Array.from(container.children).forEach((child) => observer.observe(child))
    return () => observer.disconnect()
  }, [])

  const goTo = useCallback((index: number) => {
    setCurrent(index)
  }, [])

  return (
    <>
      {/* ── Scroll container ─────────────────────────────────────── */}
      <div ref={containerRef} className={styles.container} aria-label="项目故事 · 滚动叙事">
        <Slide0Opening />
        <Slide1SocialValue />
        <Slide2Philosophy />
        <Slide3Wp11 />
        <Slide4Wp12 />
        <Slide7Closing />
      </div>

      {/* ── Progress dot navigation (fixed right) ────────────────── */}
      <nav className={styles.navDots} aria-label="章节导航">
        {Array.from({ length: SLIDE_COUNT }, (_, i) => (
          <button
            key={i}
            className={`${styles.navDot} ${i === current ? styles.navDotActive : ""}`}
            onClick={() => goTo(i)}
            aria-label={`跳转到第 ${i + 1} 屏：${SLIDE_TITLES[i] ?? ""}`}
            aria-current={i === current ? "true" : undefined}
            data-title={SLIDE_TITLES[i]}
          />
        ))}
      </nav>
    </>
  )
}
