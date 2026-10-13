"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { z } from "zod"
import { processMarkdown } from "@/lib/docs/processor"
import {
  Wp12FeedItemDetailSchema,
  Wp12FeedItemSummarySchema,
  Wp12RunResultSchema,
  Wp12RunStatusSchema,
  type Wp12FeedItemDetail,
  type Wp12FeedItemSummary,
  type Wp12RunResult,
  type Wp12RunStatus,
} from "@/lib/types/wp12"

const Wp12FeedListSchema = z.array(Wp12FeedItemSummarySchema)

async function fetchWithSchema<T>(
  url: string,
  schema: z.ZodType<T>,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  const raw: unknown = await response.json()
  return schema.parse(raw)
}

type ControllerError =
  | "feed"
  | "feedDetail"
  | "run"

export interface Wp12RunController {
  feedQuery: string
  setFeedQuery: (value: string) => void
  feedItems: Wp12FeedItemSummary[]
  isLoadingFeed: boolean
  feedError: string | null
  selectedAttackId: string | null
  setSelectedAttackId: (attackId: string) => void
  selectedFeedDetail: Wp12FeedItemDetail | null
  isLoadingFeedDetail: boolean
  feedDetailError: string | null
  runStatus: Wp12RunStatus | null
  runError: string | null
  result: Wp12RunResult | null
  planHtml: string
  planRenderError: string | null
  start: () => Promise<void>
  cancel: () => Promise<void>
  clearResult: () => void
  isStarting: boolean
  isBusy: boolean
}

export function useWp12RunController(): Wp12RunController {
  const [feedQuery, setFeedQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [feedItems, setFeedItems] = useState<Wp12FeedItemSummary[]>([])
  const [isLoadingFeed, setIsLoadingFeed] = useState(true)
  const [feedError, setFeedError] = useState<string | null>(null)
  const [selectedAttackId, setSelectedAttackIdState] = useState<string | null>(null)
  const [selectedFeedDetail, setSelectedFeedDetail] = useState<Wp12FeedItemDetail | null>(null)
  const [isLoadingFeedDetail, setIsLoadingFeedDetail] = useState(false)
  const [feedDetailError, setFeedDetailError] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<Wp12RunStatus | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [result, setResult] = useState<Wp12RunResult | null>(null)
  const [planHtml, setPlanHtml] = useState("")
  const [planRenderError, setPlanRenderError] = useState<string | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const clearError = useCallback((scope: ControllerError) => {
    if (scope === "feed") setFeedError(null)
    if (scope === "feedDetail") setFeedDetailError(null)
    if (scope === "run") setRunError(null)
  }, [])

  const setSelectedAttackId = useCallback((attackId: string) => {
    setSelectedAttackIdState(attackId)
  }, [])

  const loadRunResult = useCallback(async (runId: string) => {
    const nextResult = await fetchWithSchema(
      `/api/wp12/runs/${runId}/result`,
      Wp12RunResultSchema
    )
    setResult(nextResult)
    setSelectedAttackIdState(nextResult.attack_id)
    setRunError(null)
  }, [])

  const applyRunStatus = useCallback((snapshot: Wp12RunStatus) => {
    setRunStatus(snapshot)
    if (snapshot.attack_id) {
      setSelectedAttackIdState(snapshot.attack_id)
    }
    if (snapshot.status === "failed" && snapshot.error) {
      setRunError(snapshot.error)
    }
  }, [])

  const pollRun = useCallback(
    (runId: string) => {
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const snapshot = await fetchWithSchema(
            `/api/wp12/runs/${runId}`,
            Wp12RunStatusSchema
          )
          applyRunStatus(snapshot)

          if (snapshot.status === "queued" || snapshot.status === "running" || snapshot.status === "cancelling") {
            return
          }

          stopPolling()
          if (snapshot.status === "succeeded") {
            await loadRunResult(runId)
          }
        } catch {
          // Keep polling on transient failures.
        }
      }, 2000)
    },
    [applyRunStatus, loadRunResult, stopPolling]
  )

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(feedQuery.trim())
    }, 250)
    return () => window.clearTimeout(timer)
  }, [feedQuery])

  useEffect(() => {
    let cancelled = false
    setIsLoadingFeed(true)
    clearError("feed")

    void fetchWithSchema(
      `/api/wp12/feed?limit=50&q=${encodeURIComponent(debouncedQuery)}`,
      Wp12FeedListSchema
    )
      .then((items) => {
        if (cancelled) return
        setFeedItems(items)
      })
      .catch((error) => {
        if (cancelled) return
        setFeedError(String(error))
      })
      .finally(() => {
        if (cancelled) return
        setIsLoadingFeed(false)
      })

    return () => {
      cancelled = true
    }
  }, [clearError, debouncedQuery])

  useEffect(() => {
    if (!selectedAttackId) {
      setSelectedFeedDetail(null)
      setFeedDetailError(null)
      return
    }

    let cancelled = false
    setIsLoadingFeedDetail(true)
    clearError("feedDetail")

    void fetchWithSchema(
      `/api/wp12/feed/${encodeURIComponent(selectedAttackId)}`,
      Wp12FeedItemDetailSchema
    )
      .then((detail) => {
        if (cancelled) return
        setSelectedFeedDetail(detail)
      })
      .catch((error) => {
        if (cancelled) return
        setFeedDetailError(String(error))
      })
      .finally(() => {
        if (cancelled) return
        setIsLoadingFeedDetail(false)
      })

    return () => {
      cancelled = true
    }
  }, [clearError, selectedAttackId])

  useEffect(() => {
    let cancelled = false

    async function restore() {
      try {
        const activeResponse = await fetch("/api/wp12/runs/active", {
          cache: "no-store",
        })
        if (activeResponse.ok) {
          const raw: unknown = await activeResponse.json()
          const active = Wp12RunStatusSchema.parse(raw)
          if (cancelled) return
          applyRunStatus(active)
          pollRun(active.run_id)
          return
        }

        if (activeResponse.status !== 404) {
          throw new Error(`HTTP ${activeResponse.status}`)
        }

        const latestResponse = await fetch("/api/wp12/runs/latest/result", {
          cache: "no-store",
        })
        if (!latestResponse.ok) {
          if (latestResponse.status === 404 || cancelled) return
          throw new Error(`HTTP ${latestResponse.status}`)
        }

        const raw: unknown = await latestResponse.json()
        const latest = Wp12RunResultSchema.parse(raw)
        if (cancelled) return
        setResult(latest)
        setSelectedAttackIdState(latest.attack_id)
      } catch (error) {
        if (cancelled) return
        setRunError(`恢复状态失败: ${String(error)}`)
      }
    }

    void restore()
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [applyRunStatus, pollRun, stopPolling])

  useEffect(() => {
    let cancelled = false

    if (!result?.plan_markdown.trim()) {
      setPlanHtml("")
      setPlanRenderError(null)
      return
    }

    void processMarkdown(result.plan_markdown)
      .then((html) => {
        if (cancelled) return
        setPlanHtml(html)
        setPlanRenderError(null)
      })
      .catch((error) => {
        if (cancelled) return
        setPlanHtml("")
        setPlanRenderError(String(error))
      })

    return () => {
      cancelled = true
    }
  }, [result])

  const start = useCallback(async () => {
    if (!selectedAttackId) return

    setIsStarting(true)
    clearError("run")

    try {
      const response = await fetch("/api/wp12/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attack_id: selectedAttackId,
          tenant_id: "dashboard",
          scenario_id: "dashboard-manual",
        }),
      })
      const body = (await response.json().catch(() => null)) as unknown
      if (!response.ok) {
        const detail =
          typeof body === "object" && body !== null && "detail" in body
            ? String((body as { detail?: unknown }).detail ?? `HTTP ${response.status}`)
            : `HTTP ${response.status}`
        throw new Error(detail)
      }

      const snapshot = Wp12RunStatusSchema.parse(body)
      applyRunStatus(snapshot)
      pollRun(snapshot.run_id)
    } catch (error) {
      setRunError(String(error))
    } finally {
      setIsStarting(false)
    }
  }, [applyRunStatus, clearError, pollRun, selectedAttackId])

  const cancel = useCallback(async () => {
    if (!runStatus) return
    try {
      const snapshot = await fetchWithSchema(
        `/api/wp12/runs/${runStatus.run_id}`,
        Wp12RunStatusSchema,
        { method: "DELETE" }
      )
      applyRunStatus(snapshot)
      if (snapshot.status === "cancelling") {
        pollRun(snapshot.run_id)
      }
    } catch (error) {
      setRunError(`取消失败: ${String(error)}`)
    }
  }, [applyRunStatus, pollRun, runStatus])

  const clearResult = useCallback(() => {
    setResult(null)
    setPlanHtml("")
    setPlanRenderError(null)
  }, [])

  const isBusy =
    isStarting ||
    runStatus?.status === "queued" ||
    runStatus?.status === "running" ||
    runStatus?.status === "cancelling"

  return {
    feedQuery,
    setFeedQuery,
    feedItems,
    isLoadingFeed,
    feedError,
    selectedAttackId,
    setSelectedAttackId,
    selectedFeedDetail,
    isLoadingFeedDetail,
    feedDetailError,
    runStatus,
    runError,
    result,
    planHtml,
    planRenderError,
    start,
    cancel,
    clearResult,
    isStarting,
    isBusy,
  }
}
