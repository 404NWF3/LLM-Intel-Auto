"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import useSWR from "swr"
import { USE_MOCK_API, fetchValidated } from "@/lib/api/client"
import { MOCK_RUN_STATUS } from "@/lib/api/mock"
import {
  WpRunStatusSchema,
  type WpRunRequest,
  type WpRunStatus,
} from "@/lib/types/dashboard"
import { findWp } from "@/lib/wp-registry"

export function useWpRun(wpId: string): {
  activeRun: WpRunStatus | undefined
  isStarting: boolean
  isCancelling: boolean
  start: (req: WpRunRequest) => Promise<WpRunStatus>
  cancel: (runId: string) => Promise<void>
} {
  const wp = findWp(wpId)
  const [isStarting, setIsStarting] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [shouldPoll, setShouldPoll] = useState(false)
  const mockRunRef = useRef<WpRunStatus | null>(null)
  const mockIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [mockRun, setMockRun] = useState<WpRunStatus | undefined>(undefined)

  const { data: activeRun, mutate } = useSWR<WpRunStatus | null, Error>(
    wp && shouldPoll && !USE_MOCK_API
      ? `${wp.apiBase}/runs/active`
      : null,
    async (url: string) => {
      const res = await fetch(url)
      if (res.status === 404) return null
      if (!res.ok) throw new Error(`${res.status}`)
      const raw: unknown = await res.json()
      return WpRunStatusSchema.nullable().parse(raw)
    },
    { refreshInterval: 2000, revalidateOnFocus: false }
  )

  /* Stop polling once run completes */
  useEffect(() => {
    if (
      activeRun &&
      activeRun.status !== "running" &&
      activeRun.status !== "queued"
    ) {
      setShouldPoll(false)
    }
  }, [activeRun])

  const start = useCallback(
    async (req: WpRunRequest): Promise<WpRunStatus> => {
      if (!wp) throw new Error(`Unknown wp: ${wpId}`)
      setIsStarting(true)
      try {
        if (USE_MOCK_API) {
          await new Promise((r) => setTimeout(r, 600))
          const run: WpRunStatus = {
            ...MOCK_RUN_STATUS,
            run_id: `run_mock_${Date.now()}`,
            run_mode: req.run_mode,
            status: "running",
            progress: {
              current_node: "supervisor_plan",
              completed_nodes: ["load_runtime_context"],
              total_nodes: 21,
              percent: 5,
            },
            started_at: new Date().toISOString(),
            completed_at: null,
            errors: [],
          }
          mockRunRef.current = run
          setMockRun(run)

          // Simulate progress
          mockIntervalRef.current = setInterval(() => {
            setMockRun((prev) => {
              if (!prev || prev.status !== "running") return prev
              const nextPct = Math.min(prev.progress.percent + 5, 100)
              const isDone = nextPct >= 100
              return {
                ...prev,
                status: isDone ? "succeeded" : "running",
                progress: { ...prev.progress, percent: nextPct },
                completed_at: isDone ? new Date().toISOString() : null,
              }
            })
          }, 2000)

          return run
        }

        const res = await fetch(`${wp.apiBase}/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(req),
        })
        if (!res.ok) throw new Error(`Start run failed: ${res.status}`)
        const raw: unknown = await res.json()
        const run = WpRunStatusSchema.parse(raw)
        setShouldPoll(true)
        await mutate()
        return run
      } finally {
        setIsStarting(false)
      }
    },
    [wp, wpId, mutate]
  )

  const cancel = useCallback(
    async (runId: string) => {
      if (!wp) return
      setIsCancelling(true)
      try {
        if (USE_MOCK_API) {
          await new Promise((r) => setTimeout(r, 300))
          if (mockIntervalRef.current) {
            clearInterval(mockIntervalRef.current)
            mockIntervalRef.current = null
          }
          setMockRun(undefined)
          return
        }
        const res = await fetch(`${wp.apiBase}/runs/${runId}`, {
          method: "DELETE",
        })
        if (!res.ok) throw new Error(`Cancel failed: ${res.status}`)
        setShouldPoll(false)
        await mutate(null)
      } finally {
        setIsCancelling(false)
      }
    },
    [wp, mutate]
  )

  /* Cleanup mock interval on unmount */
  useEffect(() => {
    return () => {
      if (mockIntervalRef.current) clearInterval(mockIntervalRef.current)
    }
  }, [])

  const resolvedRun = USE_MOCK_API ? mockRun : (activeRun ?? undefined)

  return { activeRun: resolvedRun, isStarting, isCancelling, start, cancel }
}
