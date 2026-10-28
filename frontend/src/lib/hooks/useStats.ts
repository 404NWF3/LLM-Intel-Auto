"use client"

import useSWR from "swr"
import { intelFetch } from "@/lib/api/intel"
import { StatsResponseSchema, type StatsResponse } from "@/lib/types/stats"

export function useStats() {
  const { data, isLoading, isValidating, error, mutate } = useSWR<StatsResponse, Error>(
    "/api/stats",
    async (url: string) =>
      StatsResponseSchema.parse(await intelFetch(url, { cache: "no-store" })),
    { refreshInterval: 30000, revalidateOnFocus: true }
  )

  return {
    stats: data,
    isLoading,
    isValidating,
    error,
    refresh: () => mutate(),
  }
}
