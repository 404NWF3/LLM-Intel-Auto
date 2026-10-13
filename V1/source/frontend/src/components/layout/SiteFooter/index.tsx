import Link from "next/link"

const YEAR = new Date().getFullYear()

const FOOTER_COLS = [
  {
    title: "项目",
    links: [
      { href: "/", label: "首页" },
      { href: "/story", label: "项目故事" },
      { href: "/docs", label: "技术文档" },
    ],
  },
  {
    title: "WP 模块",
    links: [
      { href: "/docs/wp11-design", label: "WP1-1 情报采集" },
      { href: "/docs/wp11-design", label: "WP1-2 红队测试" },
      { href: "/docs/wp11-design", label: "WP1-3 沙盒模拟" },
      { href: "/docs/wp11-design", label: "WP1-4 异常检测" },
    ],
  },
  {
    title: "文档",
    links: [
      { href: "/docs/overview", label: "项目概览" },
      { href: "/docs/architecture", label: "系统架构" },
      { href: "/docs/frontend", label: "前端设计" },
      { href: "/dashboard", label: "控制面板" },
    ],
  },
] as const

export function SiteFooter() {
  return (
    <footer className="site-footer" role="contentinfo">
      <div className="container">
        <div className="site-footer__inner">
          {/* 品牌列 */}
          <div>
            <Link href="/" className="brand" aria-label="SUFE-SAADS 首页">
              <span className="brand__mark" aria-hidden="true">
                S
              </span>
              <span>SAADS</span>
            </Link>
            <p
              style={{
                marginTop: "0.9rem",
                fontSize: "0.92rem",
                color: "var(--text-soft)",
                maxWidth: "28ch",
                lineHeight: 1.6,
              }}
            >
              基于多智能体的 AI 系统态势感知与自动化防御系统
            </p>
            <p
              style={{
                marginTop: "1.5rem",
                fontSize: "0.82rem",
                color: "var(--text-faint)",
              }}
            >
              © {YEAR} SUFE-SAADS 项目组
            </p>
          </div>

          {/* 导航列 */}
          {FOOTER_COLS.map((col) => (
            <div key={col.title}>
              <p className="footer-title">{col.title}</p>
              <nav className="footer-links" aria-label={`${col.title}导航`}>
                {col.links.map(({ href, label }) => (
                  <Link key={label} href={href}>
                    {label}
                  </Link>
                ))}
              </nav>
            </div>
          ))}
        </div>
      </div>
    </footer>
  )
}
