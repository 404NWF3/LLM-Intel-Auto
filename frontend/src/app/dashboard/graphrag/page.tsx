import type { Metadata } from "next"
import { GraphDashboard } from "@/components/dashboard/GraphDashboard"

export const metadata: Metadata = { title: "GraphRAG 工作台 | 运维控制台" }

export default function GraphPage() {
  return <GraphDashboard />
}
