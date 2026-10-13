import { z } from "zod"

const NullableString = z.string().nullish()
const NullableNumber = z.number().nullish()
const NullableUnknownObject = z.record(z.string(), z.unknown()).nullish()
const NullableUnknownObjectArray = z.array(z.record(z.string(), z.unknown())).nullish()

export const Wp12RunStatusEnum = z.enum([
  "queued",
  "running",
  "cancelling",
  "succeeded",
  "failed",
  "cancelled",
])
export type Wp12RunStatusValue = z.infer<typeof Wp12RunStatusEnum>

export const Wp12FeedItemSummarySchema = z.object({
  attack_id: z.string(),
  attack_code: z.string(),
  canonical_name: z.string(),
  attack_family: z.string(),
  summary: z.string(),
  severity_level: z.string(),
  last_seen_at: z.string(),
  primary_cvss_base_score: z.number(),
  primary_cvss_severity_label: z.string(),
  taxonomy_code: z.string(),
  taxonomy_name: z.string(),
  component_name: z.string(),
  asset_name: z.string(),
  active: z.boolean(),
})
export type Wp12FeedItemSummary = z.infer<typeof Wp12FeedItemSummarySchema>

export const Wp12FeedItemDetailSchema = Wp12FeedItemSummarySchema.extend({
  primary_cvss_version: NullableString,
  primary_cvss_vector: NullableString,
  component_id: NullableString,
  version_constraint_raw: NullableString,
  normalized_constraint: NullableString,
  component_impact_scope: NullableString,
  asset_id: NullableString,
  asset_type: NullableString,
  artifact_uri: NullableString,
  qa_status: NullableString,
  description: NullableString,
  exploit_preconditions: NullableString,
  attack_impact_scope: NullableString,
  attack_confidence_score: NullableNumber,
  stix_type: NullableString,
  stix_payload: NullableUnknownObject,
  component_context: NullableUnknownObject,
  published_seed_assets: NullableUnknownObjectArray,
  component_risk_overview: NullableUnknownObject,
  all_taxonomies: NullableUnknownObjectArray,
}).passthrough()
export type Wp12FeedItemDetail = z.infer<typeof Wp12FeedItemDetailSchema>

export const Wp12RunRequestSchema = z.object({
  attack_id: z.string().min(1),
  tenant_id: z.string().default("dashboard"),
  scenario_id: z.string().default("dashboard-manual"),
})
export type Wp12RunRequest = z.infer<typeof Wp12RunRequestSchema>

export const Wp12RunStatusSchema = z.object({
  run_id: z.string(),
  attack_id: z.string(),
  status: Wp12RunStatusEnum,
  current_stage: z.string().nullable().optional(),
  current_task: z.string().nullable().optional(),
  completed_stages: z.array(z.string()),
  total_stages: z.number(),
  percent: z.number(),
  started_at: z.string(),
  completed_at: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
})
export type Wp12RunStatus = z.infer<typeof Wp12RunStatusSchema>

export const Wp12RunResultSchema = z.object({
  run_id: z.string(),
  attack_id: z.string(),
  status: z.string(),
  verdict: z.string().nullable().optional(),
  package_kind: z.string().nullable().optional(),
  generation_mode: z.string().nullable().optional(),
  summary: z.record(z.string(), z.unknown()),
  plan_markdown: z.string(),
  presentation_state: z.record(z.string(), z.unknown()),
  threat_understanding: z.record(z.string(), z.unknown()),
  execution_assessment: z.record(z.string(), z.unknown()),
  package_validation: z.record(z.string(), z.unknown()),
  test_package: z.record(z.string(), z.unknown()),
  artifacts: z.object({
    persistence_path: z.string().nullable().optional(),
    raw_state_path: z.string().nullable().optional(),
    presentation_state_path: z.string().nullable().optional(),
    plan_path: z.string().nullable().optional(),
  }),
})
export type Wp12RunResult = z.infer<typeof Wp12RunResultSchema>
