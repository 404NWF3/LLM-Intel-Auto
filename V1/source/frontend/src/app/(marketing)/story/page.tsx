import type { Metadata } from "next"
import { StoryShell } from "./StoryShell"

export const metadata: Metadata = {
  title: "项目故事",
  description:
    "8 屏滚动叙事，讲述 SUFE-SAADS 从社会价值出发，到四智能体攻防闭环架构的完整故事。",
}

export default function StoryPage() {
  return <StoryShell />
}
