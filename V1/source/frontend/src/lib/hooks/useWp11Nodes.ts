"use client"

import { useCallback, useState } from "react"
import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { MOCK_WP11_NODES } from "@/lib/api/mock"
import {
  WpNodeInfoSchema,
  type WpNodeInfo,
  type WpNodeLastStatus,
} from "@/lib/types/dashboard"
import { z } from "zod"

const WpNodeInfoArraySchema = z.array(WpNodeInfoSchema)

export function useWp11Nodes(): {
  nodes: WpNodeInfo[]
  isLoading: boolean
  triggerNode: (nodeName: string) => Promise<void>
  isTriggering: Record<string, boolean>
} {
  const [isTriggering, setIsTriggering] = useState<Record<string, boolean>>({})

  const { data, isLoading, mutate } = useSWR<WpNodeInfo[], Error>(
    "/api/wp11/nodes",
    async (url: string) => {
      if (USE_MOCK_API) {
        await new Promise((r) => setTimeout(r, 60))
        return MOCK_WP11_NODES
      }
      return fetchValidated(url, WpNodeInfoArraySchema)
    },
    { revalidateOnFocus: false }
  )

  const triggerNode = useCallback(
    async (nodeName: string) => {
      setIsTriggering((prev) => ({ ...prev, [nodeName]: true }))
      try {
        if (USE_MOCK_API) {
          await new Promise((r) => setTimeout(r, 400))
          // Optimistically update last_status to succeeded
          await mutate(
            (prev) =>
              prev?.map((n) =>
                n.node_name === nodeName
                  ? ({
                      ...n,
                      last_status: "succeeded" as WpNodeLastStatus,
                      last_run_at: new Date().toISOString(),
                    } satisfies WpNodeInfo)
                  : n
              ) ?? [],
            { revalidate: false }
          )
          return
        }
        const res = await fetch(`/api/wp11/nodes/${nodeName}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        })
        if (!res.ok) throw new Error(`Trigger failed: ${res.status}`)
        await mutate()
      } finally {
        setIsTriggering((prev) => ({ ...prev, [nodeName]: false }))
      }
    },
    [mutate]
  )

  return { nodes: data ?? [], isLoading, triggerNode, isTriggering }
}
