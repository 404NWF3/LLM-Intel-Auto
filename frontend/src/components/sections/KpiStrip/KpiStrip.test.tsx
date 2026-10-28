import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { KpiStrip } from "./index"

const stats = {
  item_count: 2412,
  source_count: 6,
  core_topics_covered: 2,
  core_topics_total: 18,
  core_coverage_pct: 11.1,
  script_count: 3,
  updated_at: "2026-10-28T06:00:00+00:00",
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({ matches: true }))
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(private callback: IntersectionObserverCallback) {}
      observe(target: Element) {
        queueMicrotask(() =>
          this.callback(
            [{ isIntersecting: true, target } as IntersectionObserverEntry],
            this as unknown as IntersectionObserver
          )
        )
      }
      disconnect() {}
      unobserve() {}
    }
  )
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function mount() {
  return render(
    <SWRConfig
      value={{
        provider: () => new Map(),
        dedupingInterval: 0,
        shouldRetryOnError: false,
      }}
    >
      <KpiStrip />
    </SWRConfig>
  )
}

describe("Homepage statistics", () => {
  it("waits for real data, then updates counts and fractional coverage on refresh", async () => {
    let resolve!: (response: Response) => void
    const pending = new Promise<Response>((done) => {
      resolve = done
    })
    const request = vi
      .fn()
      .mockReturnValueOnce(pending)
      .mockResolvedValueOnce(
        Response.json({
          ...stats,
          item_count: 2413,
          core_coverage_pct: 16.7,
          core_topics_covered: 3,
        })
      )
    vi.stubGlobal("fetch", request)
    const readMockMode = vi.fn(() => "true")
    vi.stubGlobal("localStorage", { getItem: readMockMode })
    mount()
    expect(screen.getAllByLabelText("数据暂不可用")).toHaveLength(3)
    expect(screen.queryByText("0")).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("正在同步")
    await act(async () => resolve(Response.json(stats)))
    expect(await screen.findByText("2,412")).toBeInTheDocument()
    expect(screen.getByText("11.1")).toBeInTheDocument()
    expect(screen.getByText("2 / 18 类话题已有情报")).toBeInTheDocument()
    expect(screen.queryByText("OWASP LLM Top 10")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "刷新数据" }))
    expect(await screen.findByText("2,413")).toBeInTheDocument()
    expect(screen.getByText("16.7")).toBeInTheDocument()
    expect(request).toHaveBeenCalledWith(
      "/api/stats",
      expect.objectContaining({ cache: "no-store" })
    )
    expect(readMockMode).not.toHaveBeenCalled()
  })

  it("shows unavailable placeholders on failure and can retry to display genuine zeros", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(null, { status: 503 }))
        .mockResolvedValueOnce(
          Response.json({
            ...stats,
            item_count: 0,
            script_count: 0,
            source_count: 0,
            core_topics_covered: 0,
            core_coverage_pct: 0,
          })
        )
    )
    mount()
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("统计暂不可用")
    )
    expect(screen.getAllByLabelText("数据暂不可用")).toHaveLength(3)
    fireEvent.click(screen.getByRole("button", { name: "刷新数据" }))
    await waitFor(() => expect(screen.getAllByText("0")).toHaveLength(2))
    expect(screen.getByText("0.0")).toBeInTheDocument()
    expect(screen.queryByLabelText("数据暂不可用")).not.toBeInTheDocument()
  })

  it("keeps the last successful data when a later refresh fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(Response.json(stats))
        .mockRejectedValueOnce(new Error("offline"))
    )
    mount()
    await screen.findByText("2,412")
    fireEvent.click(screen.getByRole("button", { name: "刷新数据" }))
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("显示上次成功同步的数据")
    )
    expect(screen.getByText("2,412")).toBeInTheDocument()
  })
})
