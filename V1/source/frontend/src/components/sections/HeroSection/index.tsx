import Link from "next/link"
import { BookOpen, LayoutDashboard } from "lucide-react"
import { ScrollReveal } from "@/components/ui/ScrollReveal"
import { SystemStatusPanel } from "./SystemStatusPanel"
import styles from "./HeroSection.module.css"

export function HeroSection() {
  return (
    <section className="hero">
      <div className="container">
        <div className="hero__layout">
          {/* ── Left: content ─────────────────────────────────────── */}
          <div className="hero__content">
            <ScrollReveal delay={0}>
              <span className="eyebrow">SUFE · 2026 · AI Security</span>
            </ScrollReveal>

            <ScrollReveal delay={1}>
              <h1 className="hero__title">
                AI 系统
                <br />
                态势感知与
                <span className={styles.titleAccent}>防御</span>
              </h1>
            </ScrollReveal>

            <ScrollReveal delay={2}>
              <p className="lead">
                基于多智能体协作，构建从威胁情报采集、自动渗透测试到沙盒模拟、异常检测的全链路
                AI 安全防御体系。
              </p>
            </ScrollReveal>

            <ScrollReveal delay={3}>
              <div className="hero__actions">
                <Link href="/story" className="button button--primary">
                  <BookOpen size={16} aria-hidden="true" />
                  了解项目故事
                </Link>
                <Link href="/dashboard" className="button button--secondary">
                  进入控制面板
                  <LayoutDashboard size={16} aria-hidden="true" />
                </Link>
              </div>
            </ScrollReveal>

            <ScrollReveal delay={4}>
              <a
                href="#kpi-strip"
                className={styles.scrollIndicator}
                aria-label="滚动到关键指标"
              >
                <span>滚动探索</span>
                <span className={styles.scrollArrow} aria-hidden="true">
                  ↓
                </span>
              </a>
            </ScrollReveal>
          </div>

          {/* ── Right: System Status Panel ────────────────────────── */}
          <ScrollReveal delay={2}>
            <SystemStatusPanel />
          </ScrollReveal>
        </div>
      </div>
    </section>
  )
}
