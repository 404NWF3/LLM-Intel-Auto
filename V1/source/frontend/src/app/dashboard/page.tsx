import type { Metadata } from "next"
import { redirect } from "next/navigation"

export const metadata: Metadata = {
  title: "控制台入口 · 运维控制台",
}

export default function DashboardPage() {
  redirect("/dashboard/wp11")
}
