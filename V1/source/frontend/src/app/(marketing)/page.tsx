import type { Metadata } from "next"
import { HeroSection } from "@/components/sections/HeroSection"
import { ArchitectureFlow } from "@/components/sections/ArchitectureFlow"
import { CtaBand } from "@/components/sections/CtaBand"

export const metadata: Metadata = {
  title: "AI 系统态势感知与自动化防御",
  description:
    "构建自我感知、学习、规划、执行的智能体群，解决 AI 系统的网络安全与功能安全挑战。",
}

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <ArchitectureFlow />
      <CtaBand />
    </>
  )
}
