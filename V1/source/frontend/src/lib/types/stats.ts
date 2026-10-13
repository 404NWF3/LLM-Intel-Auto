import { z } from "zod"

export const StatsResponseSchema = z.object({
  attack_entry_count: z.number(),
  eval_job_count: z.number(),
  owasp_covered: z.number(),
  owasp_coverage_pct: z.number(),
})

export type StatsResponse = z.infer<typeof StatsResponseSchema>
