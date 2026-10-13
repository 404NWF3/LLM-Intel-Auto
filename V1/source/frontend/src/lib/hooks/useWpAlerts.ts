"use client"

import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { MOCK_ALERTS } from "@/lib/api/mock"
import { WpAlertSchema, type WpAlert } from "@/lib/types/wp"
import { findWp } from "@/lib/wp-registry"
import { z } from "zod"

const WpAlertArraySchema = z.array(WpAlertSchema)

/** wpId=undefined → 全局告警 /api/alerts */
export function useWpAlerts(wpId?: string): {
  alerts: WpAlert[]
  isLoading: boolean
  error: Error | undefined
} {
  const wp = wpId ? findWp(wpId) : undefined
  const url = wp ? `${wp.apiBase}/alerts?limit=20` : "/api/alerts?limit=10"

  const { data, isLoading, error } = useSWR<WpAlert[], Error>(
    url,
    async (u: string) => {
      if (USE_MOCK_API) {
        await new Promise((r) => setTimeout(r, 50))
        return MOCK_ALERTS
      }
      return fetchValidated(u, WpAlertArraySchema)
    },
    { refreshInterval: 10000, revalidateOnFocus: false }
  )

  return {
    alerts: data ?? [],
    isLoading,
    error: error as Error | undefined,
  }
}
