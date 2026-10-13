"use client"

import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { MOCK_WP11_STATE } from "@/lib/api/mock"
import {
  WP11StateSnapshotSchema,
  type WP11StateSnapshot,
} from "@/lib/types/dashboard"

export function useWp11State(runId?: string): {
  snapshot: WP11StateSnapshot | undefined
  isLoading: boolean
  error: Error | undefined
} {
  const url = runId
    ? `/api/wp11/runs/${runId}/state`
    : "/api/wp11/state/latest"

  const { data, isLoading, error } = useSWR<WP11StateSnapshot, Error>(
    url,
    async (u: string) => {
      if (USE_MOCK_API) {
        await new Promise((r) => setTimeout(r, 50))
        return MOCK_WP11_STATE
      }
      return fetchValidated(u, WP11StateSnapshotSchema)
    },
    { refreshInterval: 5000, revalidateOnFocus: false }
  )

  return {
    snapshot: data,
    isLoading,
    error: error as Error | undefined,
  }
}
