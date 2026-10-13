"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { processMarkdown } from "@/lib/docs/processor"

export type CollectMode = "full" | "nvd" | "github" | "arxiv" | "community"
export type TriggerMode = "subprocess" | "openclaw"
export type ConnectionStatus = "ready" | "degraded" | "error"
export type RunStatus =
  | "starting"
  | "running"
  | "cancelling"
  | "succeeded"
  | "failed"
  | "cancelled"

export interface ConnectionSnapshot {
  status: ConnectionStatus
  checked_at: string
  workspace_root: string
  workspace_exists: boolean
  workspace_source: string
  preferred_transport: TriggerMode
  issues: string[]
  agent: {
    id: string
    configured: boolean
    workspace: string | null
    workspace_matches: boolean
  }
  gateway: {
    http_url: string
    responses_url: string
    ws_url: string
    surface: "responses" | "subprocess-fallback"
    auth_configured: boolean
    reachable: boolean
    models_ready: boolean
    protocol: number | null
    server_version: string | null
    default_agent_id: string | null
  }
  hooks: {
    enabled: boolean
    mapping_present: boolean
  }
}

interface RunResponse {
  run_id: string
  status: RunStatus
  mode: CollectMode
  transport: TriggerMode
  use_gateway: boolean
  started_at: string
  ended_at?: string | null
  error?: string | null
  assistant_markdown?: string | null
}

export type RunState =
  | { phase: "idle" }
  | { phase: "starting" }
  | {
      phase: "running"
      runId: string
      mode: CollectMode
      transport: TriggerMode
      startedAt: string
    }
  | { phase: "cancelling"; runId: string }
  | { phase: "done"; runId: string; outcome: "succeeded" | "cancelled" }
  | { phase: "error"; message: string }

interface StoredAssistantMessage {
  runId: string
  markdown: string
}

const STORAGE_KEY = "sentinel:last-assistant-message:v1"
const CLEARED_RUN_KEY = "sentinel:cleared-run-id:v1"

export interface SentinelRunController {
  collectMode: CollectMode
  setCollectMode: (mode: CollectMode) => void
  triggerMode: TriggerMode
  setTriggerMode: (mode: TriggerMode) => void
  runState: RunState
  connection: ConnectionSnapshot | null
  connectionError: string | null
  loadingConnection: boolean
  assistantMarkdown: string
  assistantHtml: string
  assistantRenderError: string | null
  refreshConnection: () => Promise<void>
  start: () => Promise<void>
  cancel: () => Promise<void>
  reset: () => void
  isStarting: boolean
  isBusy: boolean
  openClawReady: boolean
}

export function useSentinelRunController(): SentinelRunController {
  const [collectMode, setCollectMode] = useState<CollectMode>("full")
  const [triggerMode, setTriggerMode] = useState<TriggerMode>("openclaw")
  const [runState, setRunState] = useState<RunState>({ phase: "idle" })
  const [connection, setConnection] = useState<ConnectionSnapshot | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [loadingConnection, setLoadingConnection] = useState(true)
  const [assistantRunId, setAssistantRunId] = useState<string | null>(null)
  const [assistantMarkdown, setAssistantMarkdown] = useState("")
  const [assistantHtml, setAssistantHtml] = useState("")
  const [assistantRenderError, setAssistantRenderError] = useState<string | null>(null)
  const [dismissedRunId, setDismissedRunId] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const autoSelectedTransportRef = useRef(false)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const applyRunSnapshot = useCallback(
    (data: RunResponse) => {
      const nextMarkdown = data.assistant_markdown?.trim()
      if (nextMarkdown && data.run_id !== dismissedRunId) {
        setAssistantRunId(data.run_id)
        setAssistantMarkdown(data.assistant_markdown ?? "")
      }

      if (data.status === "starting" || data.status === "running") {
        setRunState({
          phase: "running",
          runId: data.run_id,
          mode: data.mode,
          transport: data.transport,
          startedAt: data.started_at,
        })
        return
      }

      if (data.status === "cancelling") {
        setRunState({ phase: "cancelling", runId: data.run_id })
        return
      }

      if (data.status === "succeeded") {
        setRunState({ phase: "done", runId: data.run_id, outcome: "succeeded" })
        return
      }

      if (data.status === "cancelled") {
        setRunState({ phase: "done", runId: data.run_id, outcome: "cancelled" })
        return
      }

      setRunState({ phase: "error", message: data.error ?? "任务执行失败" })
    },
    [dismissedRunId]
  )

  useEffect(() => {
    try {
      const clearedRunId = window.localStorage.getItem(CLEARED_RUN_KEY)
      if (clearedRunId) {
        setDismissedRunId(clearedRunId)
      }

      const raw = window.localStorage.getItem(STORAGE_KEY)
      if (!raw) return

      const stored = JSON.parse(raw) as StoredAssistantMessage
      if (!stored.runId || !stored.markdown.trim()) return
      if (stored.runId === clearedRunId) return

      setAssistantRunId(stored.runId)
      setAssistantMarkdown(stored.markdown)
    } catch {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  useEffect(() => {
    if (dismissedRunId) {
      window.localStorage.setItem(CLEARED_RUN_KEY, dismissedRunId)
    } else {
      window.localStorage.removeItem(CLEARED_RUN_KEY)
    }
  }, [dismissedRunId])

  useEffect(() => {
    if (!assistantRunId || !assistantMarkdown.trim() || assistantRunId === dismissedRunId) {
      window.localStorage.removeItem(STORAGE_KEY)
      return
    }

    const payload: StoredAssistantMessage = {
      runId: assistantRunId,
      markdown: assistantMarkdown,
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  }, [assistantMarkdown, assistantRunId, dismissedRunId])

  useEffect(() => {
    let cancelled = false

    if (!assistantMarkdown.trim()) {
      setAssistantHtml("")
      setAssistantRenderError(null)
      return
    }

    void processMarkdown(assistantMarkdown)
      .then((html) => {
        if (cancelled) return
        setAssistantHtml(html)
        setAssistantRenderError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setAssistantHtml("")
        setAssistantRenderError(String(err))
      })

    return () => {
      cancelled = true
    }
  }, [assistantMarkdown])

  const startPolling = useCallback(
    (runId: string) => {
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`/api/sentinel/runs/${runId}`, { cache: "no-store" })
          if (!res.ok) {
            stopPolling()
            setRunState({ phase: "error", message: `无法获取运行状态（HTTP ${res.status}）` })
            return
          }

          const data = (await res.json()) as RunResponse
          if (
            data.status === "starting" ||
            data.status === "running" ||
            data.status === "cancelling"
          ) {
            applyRunSnapshot(data)
            return
          }

          stopPolling()
          applyRunSnapshot(data)
        } catch {
          // Keep polling on transient fetch failures.
        }
      }, 2000)
    },
    [applyRunSnapshot, stopPolling]
  )

  const refreshConnection = useCallback(async () => {
    setLoadingConnection(true)
    setConnectionError(null)

    try {
      const res = await fetch("/api/sentinel/connection", { cache: "no-store" })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data = (await res.json()) as ConnectionSnapshot
      setConnection(data)

      if (!autoSelectedTransportRef.current) {
        setTriggerMode(data.preferred_transport)
        autoSelectedTransportRef.current = true
      }
    } catch (err) {
      setConnectionError(String(err))
    } finally {
      setLoadingConnection(false)
    }
  }, [])

  const restoreActiveRun = useCallback(async () => {
    try {
      const res = await fetch("/api/sentinel/runs/active", { cache: "no-store" })
      if (res.status === 404) {
        return
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data = (await res.json()) as RunResponse
      applyRunSnapshot(data)
      startPolling(data.run_id)
    } catch (err) {
      setRunState({ phase: "error", message: `恢复运行状态失败：${String(err)}` })
    }
  }, [applyRunSnapshot, startPolling])

  useEffect(() => {
    void refreshConnection()
    void restoreActiveRun()

    return () => stopPolling()
  }, [refreshConnection, restoreActiveRun, stopPolling])

  const start = useCallback(async () => {
    if (triggerMode === "openclaw" && connection?.preferred_transport !== "openclaw") {
      setRunState({
        phase: "error",
        message: connection?.issues?.[0] ?? "OpenClaw HTTP Responses 未就绪",
      })
      return
    }

    setRunState({ phase: "starting" })

    try {
      const res = await fetch("/api/sentinel/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: collectMode,
          transport: triggerMode,
          use_gateway: triggerMode === "openclaw",
        }),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        setRunState({ phase: "error", message: body.detail ?? `HTTP ${res.status}` })
        await refreshConnection()
        return
      }

      const data = (await res.json()) as RunResponse
      applyRunSnapshot(data)
      startPolling(data.run_id)
      await refreshConnection()
    } catch (err) {
      setRunState({ phase: "error", message: String(err) })
    }
  }, [applyRunSnapshot, collectMode, connection, refreshConnection, startPolling, triggerMode])

  const cancel = useCallback(async () => {
    if (runState.phase !== "running") return

    const { runId } = runState
    setRunState({ phase: "cancelling", runId })

    try {
      const res = await fetch(`/api/sentinel/runs/${runId}`, { method: "DELETE" })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      startPolling(runId)
    } catch (err) {
      stopPolling()
      setRunState({ phase: "error", message: `取消失败：${String(err)}` })
    }
  }, [runState, startPolling, stopPolling])

  const reset = useCallback(() => {
    stopPolling()
    setRunState({ phase: "idle" })
    setDismissedRunId(assistantRunId)
    setAssistantRunId(null)
    setAssistantMarkdown("")
    setAssistantHtml("")
    setAssistantRenderError(null)
  }, [assistantRunId, stopPolling])

  const isStarting = runState.phase === "starting"
  const isBusy = runState.phase === "running" || runState.phase === "cancelling" || isStarting
  const openClawReady =
    connection?.preferred_transport === "openclaw" && connection?.gateway.models_ready === true

  return {
    collectMode,
    setCollectMode,
    triggerMode,
    setTriggerMode,
    runState,
    connection,
    connectionError,
    loadingConnection,
    assistantMarkdown,
    assistantHtml,
    assistantRenderError,
    refreshConnection,
    start,
    cancel,
    reset,
    isStarting,
    isBusy,
    openClawReady,
  }
}
