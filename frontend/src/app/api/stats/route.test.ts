// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest"
import { GET } from "./route"

const stats = {
  item_count: 12,
  source_count: 2,
  core_topics_covered: 1,
  core_topics_total: 18,
  core_coverage_pct: 5.6,
  script_count: 3,
  updated_at: "2026-10-28T06:00:00+00:00",
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe("Stats proxy", () => {
  it("reads the configured current backend without caching", async () => {
    vi.stubEnv("INTEL_API_URL", "http://intel.test:8001/")
    const request = vi.fn().mockResolvedValue(Response.json(stats))
    vi.stubGlobal("fetch", request)
    const response = await GET()
    expect(response.status).toBe(200)
    expect(response.headers.get("cache-control")).toBe("no-store")
    expect(await response.json()).toEqual(stats)
    expect(request).toHaveBeenCalledWith(
      "http://intel.test:8001/api/stats",
      expect.objectContaining({ cache: "no-store" })
    )
  })

  it.each(["offline", "http", "legacy"])(
    "reports unavailable instead of zero for %s responses",
    async (kind) => {
      vi.spyOn(console, "error").mockImplementation(() => {})
      const request = vi.fn()
      if (kind === "offline") request.mockRejectedValue(new Error("offline"))
      else if (kind === "http")
        request.mockResolvedValue(new Response(null, { status: 503 }))
      else request.mockResolvedValue(Response.json({ attack_entry_count: 12 }))
      vi.stubGlobal("fetch", request)
      const response = await GET()
      expect(response.status).toBe(503)
      expect(await response.json()).toEqual({ detail: "统计暂不可用，请检查后端服务。" })
    }
  )
})
