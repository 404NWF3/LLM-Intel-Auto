"use client"

import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { MOCK_WP11_STATUS, MOCK_WP_STATUS_STUBS } from "@/lib/api/mock"
import { WpStatusSchema, type WpStatusResponse } from "@/lib/types/wp"
import { findWp } from "@/lib/wp-registry"

export function useWpStatus(wpId: string): {
  data: WpStatusResponse | undefined
  isLoading: boolean
  error: Error | undefined
  mutate: () => void
} {
  const wp = findWp(wpId)

  const { data, isLoading, error, mutate } = useSWR<WpStatusResponse, Error>(
    wp ? `${wp.apiBase}/status` : null,
    async (url: string) => {
      if (USE_MOCK_API) {
        await new Promise((r) => setTimeout(r, 80))
        if (wpId === "wp11") return MOCK_WP11_STATUS
        return MOCK_WP_STATUS_STUBS[wpId] ?? MOCK_WP_STATUS_STUBS["wp12"]!
      }
      return fetchValidated(url, WpStatusSchema)
    },
    { refreshInterval: 5000, revalidateOnFocus: false }
  )

  return { data, isLoading, error: error as Error | undefined, mutate }
}
