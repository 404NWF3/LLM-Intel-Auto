"use client"

import useSWR from "swr"
import { intelFetch } from "./intel"

export interface ResearchDataset {
  dataset_id: string
  name: string
  rows: number
  columns: string[]
  numeric_columns: string[]
  suggested_label: string | null
}

export interface ResearchConfig {
  dataset_id: string
  label_column: string | null
  max_rounds: number
  use_llm: boolean
}

export interface ResearchRound {
  round: number
  model: "isolation_forest" | "lof" | "pca"
  params: Record<string, number>
  reason: string
  planner: "llm" | "fallback" | "baseline"
  score: number | null
  status: "keep" | "discard" | "failed"
  duration_seconds: number
  error: string | null
}

export interface ResearchRun {
  run_id: string
  status: "running" | "cancelling" | "cancelled" | "succeeded" | "failed" | "interrupted"
  created_at: string
  updated_at: string
  config: ResearchConfig
  dataset: ResearchDataset
  current_round: number
  rounds: ResearchRound[]
  best_round: number | null
  metric: "validation_ap" | "rank_stability" | null
  evaluation_note: string
  message: string
  events: { ts: string; message: string }[]
  final_metrics: { ap: number; auroc: number } | null
  error: string | null
  artifacts_ready: boolean
  feature_columns?: string[]
  ignored_columns?: string[]
}

export interface ResearchOverview {
  active: ResearchRun | null
  run_count: number
  llm_available: boolean
  model: string
}

export const researcherFetch = intelFetch

export function useResearcherOverview() {
  return useSWR<ResearchOverview, Error>("/api/researcher/overview", researcherFetch, {
    refreshInterval: 4000,
  })
}

export async function uploadResearchDataset(file: File): Promise<ResearchDataset> {
  if (file.size > 8 * 1024 * 1024) throw new Error("CSV 文件不能超过 8 MiB。")
  const response = await fetch(
    `/api/researcher/datasets?${new URLSearchParams({ filename: file.name })}`,
    { method: "POST", headers: { "Content-Type": "text/csv" }, body: file }
  )
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(
      typeof body?.detail === "string" ? body.detail : `上传失败（${response.status}），请重试。`
    )
  }
  return response.json()
}

export function researchArtifactUrl(runId: string, artifact: "model" | "scores") {
  return `/api/researcher/runs/${encodeURIComponent(runId)}/${artifact}`
}

export const RESEARCH_MODEL_NAMES: Record<ResearchRound["model"], string> = {
  isolation_forest: "Isolation Forest",
  lof: "Local Outlier Factor",
  pca: "PCA 重构",
}

export const RESEARCH_STATUS_NAMES: Record<ResearchRun["status"], string> = {
  running: "建模中",
  cancelling: "正在停止",
  cancelled: "已停止",
  succeeded: "已完成",
  failed: "失败",
  interrupted: "已中断",
}

export function isResearchActive(run?: ResearchRun | null) {
  return run?.status === "running" || run?.status === "cancelling"
}
