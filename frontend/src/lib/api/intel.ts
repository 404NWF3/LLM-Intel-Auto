"use client"

import useSWR from "swr"

export interface IntelRun {
  run_id: string
  status: string
  saved_at: string
  run_mode: string
  item_count: number
  rounds: number
  error?: string | null
  stop_reason?: string | null
}
export interface IntelOverview {
  active: IntelRun | null
  item_count: number
  run_count: number
  sources: string[]
  topics: string[]
  coverage: Record<string, number>
  latest: {
    run_id: string
    status: string
    saved_at: string
    summary: Record<string, unknown>
  } | null
}
export interface IntelItem {
  item_id: string
  title: string
  summary: string | null
  source_name: string
  source_uri: string | null
  published_at: string | null
  relevance_score: number
  topics: string[] | null
}
export interface IntelDetail {
  run_id: string
  status: string
  error: string | null
  summary: { rounds?: number; raw_items?: number; stop_reason?: string }
  metrics: { api_calls_used?: number; elapsed_seconds?: number }
  events: { ts: string; event: string; message: string }[]
  errors: { error_type: string; message: string }[]
}
export interface IntelItemDetail extends IntelItem {
  raw_text: string | null
  metadata?: { content_scope?: string; raw_text_check?: { status?: string } }
}
export async function intelFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `请求失败（${response.status}），请检查后端 API 服务。`
    )
  }
  return response.json()
}
export async function exportIntelItems() {
  const response = await fetch("/api/intel/export", { cache: "no-store" })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `导出失败（${response.status}），请稍后重试。`
    )
  }
  if (!response.headers.get("Content-Type")?.includes("application/json")) {
    throw new Error("导出响应异常，请检查后端 API 服务。")
  }
  const filename = response.headers.get("Content-Disposition")
    ?.match(/filename="([A-Za-z0-9_.-]+)"/)?.[1] || "intel-agent-items.json"
  return { blob: await response.blob(), filename }
}
export function useIntelOverview() {
  return useSWR<IntelOverview, Error>("/api/intel/overview", intelFetch, {
    refreshInterval: 4000,
  })
}
