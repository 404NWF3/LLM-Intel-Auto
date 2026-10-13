import { z } from "zod"

/* ── 运行模式 ────────────────────────────────────────────────── */

export const RunModeEnum = z.enum([
  "bootstrap",
  "incremental",
  "gap_fill",
  "weak_signal_focus",
  "mixed",
])
export type RunMode = z.infer<typeof RunModeEnum>

export const RUN_MODE_LABELS: Record<RunMode, string> = {
  bootstrap: "全量采集",
  incremental: "增量更新",
  gap_fill: "缺口填补",
  weak_signal_focus: "弱信号挖掘",
  mixed: "混合模式",
}

/* ── 运行状态 ────────────────────────────────────────────────── */

export const RunStatusEnum = z.enum([
  "queued",
  "running",
  "partial_success",
  "succeeded",
  "failed",
])
export type RunStatus = z.infer<typeof RunStatusEnum>

/* ── 启动运行请求 ─────────────────────────────────────────────── */

export const WpRunRequestSchema = z.object({
  run_mode: RunModeEnum,
  target_sources: z.array(z.string()).optional(),
  runtime_context_overrides: z.record(z.string(), z.unknown()).optional(),
})
export type WpRunRequest = z.infer<typeof WpRunRequestSchema>

/* ── 运行进度 ────────────────────────────────────────────────── */

export const WpRunProgressSchema = z.object({
  current_node: z.string().nullable(),
  completed_nodes: z.array(z.string()),
  total_nodes: z.number(),
  percent: z.number().min(0).max(100),
})
export type WpRunProgress = z.infer<typeof WpRunProgressSchema>

export const WpRunErrorSchema = z.object({
  node_name: z.string(),
  error_type: z.string(),
  message: z.string(),
  occurred_at: z.string(),
})

export const WpRunStatusSchema = z.object({
  run_id: z.string(),
  status: RunStatusEnum,
  run_mode: RunModeEnum,
  progress: WpRunProgressSchema,
  started_at: z.string().datetime({ offset: true }),
  completed_at: z.string().datetime({ offset: true }).nullable().optional(),
  errors: z.array(WpRunErrorSchema),
})
export type WpRunStatus = z.infer<typeof WpRunStatusSchema>

/* ── 图节点信息（WP1-1 专属）─────────────────────────────────── */

export const WpNodeLastStatusEnum = z.enum([
  "succeeded",
  "failed",
  "skipped",
  "running",
  "never_run",
])
export type WpNodeLastStatus = z.infer<typeof WpNodeLastStatusEnum>

export const WpNodeInfoSchema = z.object({
  node_name: z.string(),
  display_name: z.string(),
  description: z.string().optional(),
  last_run_at: z.string().datetime({ offset: true }).nullable(),
  last_status: WpNodeLastStatusEnum,
  /** false 表示该节点不允许单独触发（如 load_runtime_context）*/
  is_triggerable: z.boolean(),
})
export type WpNodeInfo = z.infer<typeof WpNodeInfoSchema>

/* ── WP11GraphState 快照（精简版）───────────────────────────── */

export const WP11StateSnapshotSchema = z.object({
  run_id: z.string().nullable(),
  run_mode: z.string().nullable(),
  run_status: z.string().nullable(),
  current_node: z.string().nullable(),
  processed_count: z.number(),
  dedup_merged_count: z.number(),
  new_attack_count: z.number(),
  bom_queue_count: z.number(),
  reflection_round: z.number(),
  gap_fill_round: z.number(),
  errors_count: z.number(),
  completed_nodes: z.array(z.string()),
  raw_items_count: z.number(),
  standardized_items_count: z.number(),
  reflection_needed: z.boolean(),
  gap_fill_needed: z.boolean(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  _full_state: z.record(z.string(), z.unknown()).optional(),
})
export type WP11StateSnapshot = z.infer<typeof WP11StateSnapshotSchema>

/* ── WP1-1 图节点名称常量（来自 runtime.py node_order）──────── */

export const WP11_NODE_ORDER = [
  "load_runtime_context",
  "supervisor_plan",
  "dispatch_collection",
  "collect_structured_sources",
  "collect_code_sources",
  "collect_paper_sources",
  "collect_community_sources",
  "collect_advisory_sources",
  "store_raw_records",
  "assess_collection_yield",
  "reflect_search_strategy",
  "parse_and_standardize",
  "semantic_dedup_and_merge",
  "resolve_ai_bom",
  "review_ai_bom_resolution",
  "score_confidence_and_novelty",
  "refresh_coverage_view",
  "coverage_gap_analysis",
  "weak_signal_mining",
  "generate_alerts",
  "finalize_run",
] as const

export type WP11NodeName = (typeof WP11_NODE_ORDER)[number]
