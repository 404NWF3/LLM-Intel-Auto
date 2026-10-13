import { z } from "zod"

/* ── 基础枚举 ──────────────────────────────────────────────── */

export const WpStatusEnum = z.enum([
  "running",
  "idle",
  "warning",
  "error",
  "pending",
])
export type WpStatus = z.infer<typeof WpStatusEnum>

export const WpLayerEnum = z.enum(["generic", "user"])
export type WpLayer = z.infer<typeof WpLayerEnum>

/* ── API 响应 Schema ───────────────────────────────────────── */

export const WpStatusSchema = z.object({
  wp_id: z.string(),
  status: WpStatusEnum,
  uptime_seconds: z.number().nonnegative(),
  version: z.string(),
  metrics: z.record(z.string(), z.union([z.number(), z.string()])),
  current_tasks: z.array(z.string()).optional(),
  last_updated: z.string().datetime({ offset: true }),
})
export type WpStatusResponse = z.infer<typeof WpStatusSchema>

export const WpMetricPointSchema = z.object({
  timestamp: z.string().datetime({ offset: true }),
  value: z.number(),
})
export type WpMetricPoint = z.infer<typeof WpMetricPointSchema>

export const WpMetricSeriesSchema = z.object({
  key: z.string(),
  points: z.array(WpMetricPointSchema),
})
export type WpMetricSeries = z.infer<typeof WpMetricSeriesSchema>

export const WpAlertSchema = z.object({
  id: z.string(),
  severity: z.enum(["HIGH", "MEDIUM", "LOW"]),
  title: z.string(),
  cvss: z.number().min(0).max(10).optional(),
  created_at: z.string().datetime({ offset: true }),
})
export type WpAlert = z.infer<typeof WpAlertSchema>

export const WpLogEntrySchema = z.object({
  timestamp: z.string().datetime({ offset: true }),
  level: z.enum(["INFO", "WARN", "ERROR", "DEBUG"]),
  source: z.string(),
  message: z.string(),
})
export type WpLogEntry = z.infer<typeof WpLogEntrySchema>

/** 扩展日志条目：携带可展开的 verbose JSON 数据 */
export type WpVerboseLogEntry = WpLogEntry & {
  verboseKey?: string
  verboseJson?: string
  truncated?: boolean
}

/* ── 工具函数 ──────────────────────────────────────────────── */

/** 将 uptime_seconds 格式化为 "Xd Xh Xm" */
export function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

/** 状态对应的人类可读文字 */
export const STATUS_LABELS: Record<WpStatus, string> = {
  running: "运行中",
  idle: "空闲",
  warning: "告警",
  error: "错误",
  pending: "待接入",
}
