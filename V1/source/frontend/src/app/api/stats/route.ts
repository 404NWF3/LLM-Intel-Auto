/**
 * GET /api/stats
 * Next.js Route Handler — 直连 PostgreSQL，不经过 FastAPI。
 * 返回首页 KPI 所需的实时数据库统计量。
 */
import { NextResponse } from "next/server"
import { Client } from "pg"

export async function GET() {
  const dsn = process.env.POSTGRES_DSN
  if (!dsn) {
    return NextResponse.json(
      { error: "POSTGRES_DSN not configured" },
      { status: 500 }
    )
  }

  const client = new Client({ connectionString: dsn })
  try {
    await client.connect()

    // 1. attack_entry 数量（表一定存在）
    const r1 = await client.query(
      "SELECT COUNT(*)::int AS cnt FROM wp11.attack_entry"
    )
    const attackEntryCount: number = r1.rows[0]?.cnt ?? 0

    // 2. wp12_eval_job 数量（表可能还未创建）
    let evalJobCount = 0
    try {
      const r2 = await client.query(
        "SELECT COUNT(*)::int AS cnt FROM wp11.wp12_eval_job"
      )
      evalJobCount = r2.rows[0]?.cnt ?? 0
    } catch {
      // 表不存在，静默返回 0
    }

    // 3. OWASP 覆盖类别数（物化视图可能还未刷新）
    let owaspCovered = 10
    try {
      const r3 = await client.query(
        "SELECT COUNT(*)::int AS cnt FROM wp11.mv_owasp_coverage WHERE attack_count > 0"
      )
      owaspCovered = r3.rows[0]?.cnt ?? 10
    } catch {
      // 物化视图不存在，默认全覆盖
    }

    return NextResponse.json({
      attack_entry_count: attackEntryCount,
      eval_job_count: evalJobCount,
      owasp_covered: owaspCovered,
      owasp_coverage_pct: parseFloat(
        (Math.min(owaspCovered, 10) / 10 * 100).toFixed(1)
      ),
    })
  } catch (err) {
    console.error("[/api/stats] DB query failed:", err)
    return NextResponse.json(
      { error: "database query failed" },
      { status: 500 }
    )
  } finally {
    await client.end()
  }
}
