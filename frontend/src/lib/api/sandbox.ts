"use client"
import useSWR from "swr"
import { intelFetch } from "./intel"

export interface SandboxCapabilities {
  runtime_ready: boolean
  model_ready: boolean
  graph_index_ready: boolean
  graph_credentials_ready: boolean
  audit_ready: boolean
  case_ready: boolean
  graph_build_ready: boolean
  graph: GraphManifest | null
  model: string | null
  graph_root: string
  families: string[]
}
export interface GraphManifest {
  status: string
  run_id: string
  retrieval_mode: string
  indexed_items: number
  available_items: number
  matching_items: number
  built_at: string
  corpus_sha256: string
  selection: { limit: number; focus: string }
  counts: Record<string, number>
}
export interface SandboxOverview {
  capabilities: SandboxCapabilities
  active_run_id: string | null
  active_run_kind: "audit" | "case" | "graph" | null
  recent_run_count: number
  recent_completed_count: number
}
export interface SandboxConfig {
  kind: "audit" | "case"
  target_repo: string
  authorization_ref: string
  goal: string
  request: string
  max_rounds: number
  max_agent_calls: number
  max_cost_usd: number
  use_graphrag: boolean
}
export interface SandboxRun {
  run_id: string
  kind: "audit" | "case" | "graph"
  status: string
  created_at: string
  updated_at: string
  title: string
  error: string | null
  config: SandboxConfig
  attempts: number
}
export interface Finding {
  finding_id: string
  severity: string
  confidence: string
  root_cause: string
  impact: string
  remediation: string
  code_evidence_ids: string[]
  graph_evidence_ids: string[]
  judge_rationale: string[]
  attack_path: string[]
}
export interface SandboxDetail extends SandboxRun {
  phase: string
  graph_progress?: {
    phase: string
    completed: string[]
    total: number
    indexed_items: number
    counts?: Record<string, number>
  } | null
  state: {
    profile: Record<string, unknown> | null
    threat_surfaces: { surface_id: string; name: string; kind: string }[] | null
    hypotheses: Record<
      string,
      { status: string; hypothesis: { title?: string; hypothesis_id: string } }
    > | null
    findings: Finding[] | null
    agent_calls_used: number | null
    cost_usd_used: number | null
    graph_enabled: boolean | null
    graph_skipped_reason: string | null
  }
  case: Record<string, unknown> | null
  logs: string[]
  events: { source: string; data: Record<string, unknown> }[]
  artifacts: { path: string; name: string; size: number }[]
  can_resume: boolean
}
export const sandboxFetch = intelFetch
export function useSandboxOverview() {
  return useSWR<SandboxOverview, Error>("/api/sandbox/overview", sandboxFetch, {
    refreshInterval: 4000,
  })
}
export function useSandboxRuns(workspace: "sandbox" | "graph") {
  return useSWR<SandboxRun[], Error>(
    `/api/sandbox/runs?workspace=${workspace}`,
    sandboxFetch,
    { refreshInterval: 4000 }
  )
}
export function artifactUrl(runId: string, path: string) {
  return `/api/sandbox/runs/${encodeURIComponent(runId)}/artifact?${new URLSearchParams({ path })}`
}
