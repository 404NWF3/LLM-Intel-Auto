"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, Menu, X } from "lucide-react"
import styles from "./SiteHeader.module.css"

const NAV_LINKS = [
  { href: "/", label: "首页" },
  { href: "/story", label: "项目故事" },
  { href: "/docs", label: "技术文档" },
  { href: "/dashboard", label: "控制面板" },
] as const

export function SiteHeader() {
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <header className="site-header" role="banner">
      <div className={`container site-header__inner`}>
        {/* Logo */}
        <Link href="/" className="brand" aria-label="SUFE-SAADS 首页">
          <span className="brand__mark" aria-hidden="true">
            S
          </span>
          <span>SAADS</span>
        </Link>

        {/* 桌面端导航 */}
        <nav className="nav" aria-label="主导航">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={[
                "nav__link",
                pathname === href || (href !== "/" && pathname.startsWith(href))
                  ? styles.active
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-current={pathname === href ? "page" : undefined}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* 桌面端 CTA */}
        <div className="header-actions">
          <Link
            href="/dashboard"
            className="button button--primary"
            aria-label="进入控制面板"
          >
            <LayoutDashboard width={16} height={16} aria-hidden="true" />
            控制面板
          </Link>
        </div>

        {/* 移动端汉堡按钮 */}
        <button
          className={styles.menuBtn}
          onClick={() => setMobileOpen((v) => !v)}
          aria-label={mobileOpen ? "关闭菜单" : "打开菜单"}
          aria-expanded={mobileOpen}
          aria-controls="mobile-nav"
        >
          {mobileOpen ? (
            <X width={20} height={20} aria-hidden="true" />
          ) : (
            <Menu width={20} height={20} aria-hidden="true" />
          )}
        </button>
      </div>

      {/* 移动端下拉菜单 */}
      {mobileOpen && (
        <nav
          id="mobile-nav"
          className={styles.mobileNav}
          aria-label="移动端导航"
        >
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={[
                styles.mobileLink,
                pathname === href || (href !== "/" && pathname.startsWith(href))
                  ? styles.mobileLinkActive
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => setMobileOpen(false)}
              aria-current={pathname === href ? "page" : undefined}
            >
              {label}
            </Link>
          ))}
          <div className={styles.mobileCta}>
            <Link
              href="/dashboard"
              className="button button--primary"
              onClick={() => setMobileOpen(false)}
            >
              <LayoutDashboard width={16} height={16} aria-hidden="true" />
              进入控制面板
            </Link>
          </div>
        </nav>
      )}
    </header>
  )
}
