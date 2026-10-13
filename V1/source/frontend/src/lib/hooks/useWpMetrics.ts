"use client"

import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { generateMockMetricSeries } from "@/lib/api/mock"
import {
  WpMetricSeriesSchema,
  type WpMetricSeries,
} from "@/lib/types/wp"
import { findWp } from "@/lib/wp-registry"
import { z } from "zod"

const WpMetricSeriesArraySchema = z.array(WpMetricSeriesSchema)

const MOCK_BASES: Record<string, { base: number; growth: number }> = {
  attack_pool_size: { base: 2300, growth: 5 },
  coverage_rate: { base: 88, growth: 0.08 },
  new_intel_24h: { base: 30, growth: 0.5 },
  script_count: { base: 0, growth: 0 },
  owasp_coverage: { base: 0, growth: 0 },
  scripts_24h: { base: 0, growth: 0 },
  sessions: { base: 0, growth: 0 },
  datasets: { base: 0, growth: 0 },
  vuln_confirmed: { base: 0, growth: 0 },
  models_trained: { base: 0, growth: 0 },
  best_f1: { base: 0, growth: 0 },
  iterations: { base: 0, growth: 0 },
}

export function useWpMetrics(
  wpId: string,
  keys: string[]
): {
  series: WpMetricSeries[]
  isLoading: boolean
  error: Error | undefined
} {
  const wp = findWp(wpId)

  const { data, isLoading, error } = useSWR<WpMetricSeries[], Error>(
    wp && keys.length > 0
      ? `${wp.apiBase}/metrics?keys=${keys.join(",")}&window=48h`
      : null,
    async (url: string) => {
      if (USE_MOCK_API) {
        await new Promise((r) => setTimeout(r, 60))
        return keys.map((key) => {
          const cfg = MOCK_BASES[key] ?? { base: 0, growth: 0 }
          return generateMockMetricSeries(key, cfg.base, cfg.growth)
        })
      }
      return fetchValidated(url, WpMetricSeriesArraySchema)
    },
    { refreshInterval: 30000, revalidateOnFocus: false }
  )

  return {
    series: data ?? [],
    isLoading,
    error: error as Error | undefined,
  }
}
