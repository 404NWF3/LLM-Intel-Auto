import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import { IntelDashboard, safeSourceUrl } from "./index"

const overview = {
  active: null,
  item_count: 1,
  run_count: 1,
  sources: ["arxiv_api"],
  topics: ["prompt injection"],
  coverage: { "prompt injection": 1 },
  latest: { run_id: "saved", status: "succeeded" },
}
const item = {
  item_id: "arxiv:1",
  title: "Prompt injection research",
  summary: "Research summary",
  source_name: "arxiv_api",
  source_uri: "https://arxiv.org/abs/1",
  relevance_score: 0.9,
  topics: ["prompt injection"],
}
function mount(postStatus = 202, exportResponse?: Response | Promise<Response>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/intel/export" && exportResponse) return exportResponse
    if (init?.method === "POST")
      return new Response(
        JSON.stringify(
          postStatus === 202
            ? { run_id: "new" }
            : { detail: "已有采集任务运行中，请等待完成。" }
        ),
        { status: postStatus }
      )
    const body = url.endsWith("overview")
      ? overview
      : url.endsWith("/runs")
        ? [
            {
              run_id: "saved",
              run_mode: "bootstrap",
              item_count: 1,
              saved_at: "2026-10-14",
              status: "succeeded",
            },
          ]
        : url.includes("/items?")
          ? [item]
          : url.includes("/items/")
            ? { ...item, raw_text: "Full source content\n".repeat(3000) + "FINAL RAW MARKER" }
          : { status: "succeeded", summary: {}, metrics: {}, events: [], errors: [] }
    return new Response(JSON.stringify(body))
  })
  vi.stubGlobal("fetch", fetchMock)
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <IntelDashboard />
    </SWRConfig>
  )
  return fetchMock
}
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
describe("IntelDashboard", () => {
  it("submits budgets above the former caps and filters persisted items", async () => {
    const fetchMock = mount()
    await screen.findByText("Prompt injection research")
    fireEvent.change(screen.getByLabelText(/关注方向/), {
      target: { value: "MCP security" },
    })
    expect(screen.getByLabelText("最大轮次")).not.toHaveAttribute("max")
    expect(screen.getByLabelText("API 调用预算")).not.toHaveAttribute("max")
    fireEvent.change(screen.getByLabelText("最大轮次"), { target: { value: "200" } })
    fireEvent.change(screen.getByLabelText("API 调用预算"), {
      target: { value: "10000" },
    })
    fireEvent.click(screen.getByRole("button", { name: "开始采集" }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/intel/runs",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            mode: "incremental",
            focus: "MCP security",
            window_days: 1,
            max_rounds: 200,
            max_api_calls: 10000,
          }),
        })
      )
    )
    fireEvent.change(screen.getByLabelText("搜索情报"), { target: { value: "prompt" } })
    fireEvent.click(screen.getByRole("button", { name: "搜索" }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("text=prompt"),
        expect.anything()
      )
    )
    fireEvent.click(screen.getByRole("tab", { name: "运行历史" }))
    expect(screen.getByRole("button", { name: /全量探索.*saved/ })).toBeInTheDocument()
  })
  it("shows conflict errors instead of claiming a successful start", async () => {
    mount(409)
    await screen.findByText("Prompt injection research")
    fireEvent.click(screen.getByRole("button", { name: "开始采集" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("已有采集任务运行中")
  })
  it("rejects unsafe source links", () => {
    expect(safeSourceUrl("javascript:alert(1)")).toBeUndefined()
    expect(safeSourceUrl("https://arxiv.org/abs/123")).toBe("https://arxiv.org/abs/123")
  })
  it("loads complete raw text only when expanded", async () => {
    const fetchMock = mount()
    const summary = await screen.findByText("查看已采集原文（raw text）")
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/items/"))).toBe(false)
    const details = summary.closest("details")!
    details.open = true
    fireEvent(details, new Event("toggle"))
    expect(await screen.findByText(/FINAL RAW MARKER/)).toHaveTextContent("FINAL RAW MARKER")
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/intel/items/arxiv%3A1")).toBe(true)
  })
  it("downloads the entire library even with active filters and keeps full content", async () => {
    const rawText = "完整原文\n".repeat(3000) + "FINAL EXPORT MARKER"
    const exportBody = JSON.stringify({ item_count: 206, items: [{ ...item, raw_text: rawText }] })
    let resolveExport!: (response: Response) => void
    const exportResponse = new Promise<Response>((resolve) => { resolveExport = resolve })
    const createUrl = vi.fn<(blob: Blob) => string>(() => "blob:full-export")
    vi.stubGlobal("URL", class extends URL {
      static override createObjectURL = createUrl
      static override revokeObjectURL = vi.fn()
    })
    const clicked: { filename: string; href: string }[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push({ filename: this.download, href: this.href })
    })
    const fetchMock = mount(202, exportResponse)
    await screen.findByText(item.title)
    fireEvent.change(screen.getByLabelText("筛选来源"), { target: { value: "arxiv_api" } })
    fireEvent.click(screen.getByRole("checkbox", { name: "所选任务" }))
    fireEvent.change(screen.getByLabelText("搜索情报"), { target: { value: "prompt" } })
    fireEvent.click(screen.getByRole("button", { name: "搜索" }))
    fireEvent.click(screen.getByRole("button", { name: "下载全部完整情报" }))
    expect(screen.getByRole("button", { name: "正在准备下载…" })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith("/api/intel/export", { cache: "no-store" })
    resolveExport(new Response(exportBody, { headers: {
      "Content-Type": "application/json",
      "Content-Disposition": 'attachment; filename="intel-agent-items-test.json"',
    } }))
    await waitFor(() => expect(clicked).toEqual([
      { filename: "intel-agent-items-test.json", href: "blob:full-export" },
    ]))
    const blob = createUrl.mock.calls[0]![0]
    const downloadedText = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.onerror = () => reject(reader.error)
      reader.readAsText(blob)
    })
    expect(downloadedText).toBe(exportBody)
    expect(screen.getByRole("button", { name: "下载全部完整情报" })).toBeEnabled()
  })
  it.each([
    [503, "application/json", JSON.stringify({ detail: "情报存储暂不可用" }), "情报存储暂不可用"],
    [200, "text/html", "<html>proxy error</html>", "导出响应异常"],
  ])("shows export errors without starting a download (%s, %s)", async (status, contentType, body, message) => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    mount(202, new Response(body, { status, headers: { "Content-Type": contentType } }))
    fireEvent.click(screen.getByRole("button", { name: "下载全部完整情报" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(message)
    expect(click).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "下载全部完整情报" })).toBeEnabled()
  })
})
