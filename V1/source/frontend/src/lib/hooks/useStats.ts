"use client"

import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { MOCK_STATS } from "@/lib/api/mock"
import {
  StatsResponseSchema,
  type StatsResponse,
} from "@/lib/types/stats"

export function useStats(): {
  stats: StatsResponse | undefined
  isLoading: boolean
  error: Error | undefined
} {
  const { data, isLoading, error } = useSWR<StatsResponse, Error>(
    "/api/stats",
    async (url: string) => {
      if (USE_MOCK_API) {
        await new Promise((resolve) => setTimeout(resolve, 60))
        return MOCK_STATS
      }

      return fetchValidated(url, StatsResponseSchema)
    },
    { refreshInterval: 30000, revalidateOnFocus: false }
  )

  return {
    stats: data,
    isLoading,
    error: error as Error | undefined,
  }
}
