import type { z } from "zod"

/* ── 基础 fetch wrapper ─────────────────────────────────────── */

/**
 * 发起 GET 请求并用 Zod schema 校验响应。
 * 校验失败时抛出包含详细字段信息的错误，而非静默返回 undefined。
 */
export async function fetchValidated<T>(
  url: string,
  schema: z.ZodType<T>,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })

  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}: ${url}`)
  }

  const raw: unknown = await res.json()
  const parsed = schema.safeParse(raw)

  if (!parsed.success) {
    // 在开发环境打印完整 Zod 错误，生产环境只抛消息
    if (process.env.NODE_ENV !== "production") {
      console.error(`[fetchValidated] Zod parse error for ${url}:`, parsed.error.format())
    }
    throw new Error(
      `Response validation failed for ${url}: ${parsed.error.message}`
    )
  }

  return parsed.data
}

/* ── mock 模式开关 ──────────────────────────────────────────── */

/** localStorage key，运行时覆盖 build-time 环境变量 */
export const MOCK_MODE_STORAGE_KEY = "saads_mock_mode"

/** 构建时默认值 */
const _ENV_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_API === "true"

/**
 * 运行时 mock 模式开关：
 * 优先读取 localStorage["saads_mock_mode"]（Dashboard 切换键写入），
 * 未设置时回退到 build-time NEXT_PUBLIC_USE_MOCK_API。
 * SSR 阶段无 window，始终返回 build-time 值。
 */
export const USE_MOCK_API = (() => {
  if (typeof window === "undefined") return _ENV_MOCK
  const stored = localStorage.getItem(MOCK_MODE_STORAGE_KEY)
  return stored !== null ? stored === "true" : _ENV_MOCK
})()
