import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  preload: true,
  variable: "--font-inter",
})

export const metadata: Metadata = {
  title: {
    default: "SUFE-SAADS · AI 系统态势感知与自动化防御",
    template: "%s · SUFE-SAADS",
  },
  description:
    "基于多智能体的 AI 系统态势感知与自动化防御系统——构建自我感知、学习、规划、执行的智能体群，解决 AI 系统的网络安全与功能安全挑战。",
  keywords: ["AI 安全", "多智能体", "态势感知", "自动化防御", "大模型安全"],
  openGraph: {
    siteName: "SUFE-SAADS",
    type: "website",
    locale: "zh_CN",
  },
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={inter.variable}>
      <body className="site-shell">{children}</body>
    </html>
  )
}
