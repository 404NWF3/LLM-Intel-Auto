import { z } from "zod"

export const StatsResponseSchema = z.object({
  item_count: z.number().int().nonnegative(),
  source_count: z.number().int().nonnegative(),
  core_topics_covered: z.number().int().nonnegative(),
  core_topics_total: z.number().int().positive(),
  core_coverage_pct: z.number().min(0).max(100),
  script_count: z.number().int().nonnegative(),
  updated_at: z.string().datetime({ offset: true }),
})

export type StatsResponse = z.infer<typeof StatsResponseSchema>
