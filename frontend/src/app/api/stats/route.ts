import { NextResponse } from "next/server"
import { StatsResponseSchema } from "@/lib/types/stats"

export async function GET() {
  const baseUrl = (process.env.INTEL_API_URL || "http://127.0.0.1:8001").replace(
    /\/$/,
    ""
  )
  try {
    const response = await fetch(`${baseUrl}/api/stats`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    })
    if (!response.ok) throw new Error(`Backend returned ${response.status}`)
    const stats = StatsResponseSchema.parse(await response.json())
    return NextResponse.json(stats, { headers: { "Cache-Control": "no-store" } })
  } catch (error) {
    console.error("[/api/stats] Statistics unavailable:", error)
    return NextResponse.json(
      { detail: "统计暂不可用，请检查后端服务。" },
      { status: 503, headers: { "Cache-Control": "no-store" } }
    )
  }
}
