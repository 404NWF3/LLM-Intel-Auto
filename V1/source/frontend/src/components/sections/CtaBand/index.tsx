import Link from "next/link"
import { ArrowRight, BookOpen } from "lucide-react"
import { ScrollReveal } from "@/components/ui/ScrollReveal"

export function CtaBand() {
  return (
    <section className="section" aria-label="行动召唤">
      <div className="container">
        <ScrollReveal>
          <div className="cta-band">
            <div className="cta-band__inner">
              <div>
                <p className="eyebrow">开始探索</p>
                <h2
                  style={{
                    marginTop: "0.6rem",
                    fontSize: "clamp(1.6rem, 2.8vw, 2.4rem)",
                  }}
                >
                  从情报到防御，
                  <br />
                  全程自动化
                </h2>
                <p
                  className="lead"
                  style={{ marginTop: "0.8rem", fontSize: "1rem" }}
                >
                  了解 SUFE-SAADS 如何以四智能体协作，构建完整的 AI
                  安全防御闭环。
                </p>
              </div>

              <div className="cta-band__actions">
                <Link href="/story" className="button button--primary">
                  <BookOpen size={16} aria-hidden="true" />
                  查看项目故事
                </Link>
                <Link href="/dashboard" className="button button--secondary">
                  进入控制面板
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
