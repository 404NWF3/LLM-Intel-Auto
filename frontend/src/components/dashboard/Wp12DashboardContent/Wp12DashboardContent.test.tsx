import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { PentestDetail } from "@/lib/api/pentest"
import { Wp12DashboardContent } from "./index"

const item = {
  item_id: "arxiv:test/source",
  title: "系统提示泄漏研究",
  source_name: "arxiv_api",
  summary: "攻击性查询可能导致隐藏系统指令被输出。",
  raw_text: "采集的完整原文",
  source_uri: "https://example.test/paper",
}

function makeRun(overrides: Partial<PentestDetail> = {}): PentestDetail {
  return {
    run_id: "pentest_test",
    status: "succeeded",
    created_at: "2026-10-28T01:00:00Z",
    updated_at: "2026-10-28T01:00:05Z",
    config: { intel_id: item.item_id, focus: "", protocol: "auto" },
    intel_title: "历史任务对应的情报",
    phase: "ready",
    message: "检测脚本已生成",
    events: [],
    error: null,
    artifacts_ready: true,
    target_executed: false,
    source: {
      ...item,
      published_at: null,
      relevance_score: 0.9,
      topics: [],
      source_sha256: "abc",
      truncated_fields: [],
    },
    analysis: {
      title: "提示提取",
      disposition: "testable",
      mechanism: "系统提示边界可能被绕过",
      affected_components: ["chat"],
      preconditions: [],
      strategy: "基线与提取探针对照",
      missing_information: [],
      limitations: [],
      references: [{ field: "summary", quote: item.summary, start: 0, end: 20 }],
    },
    plan: null,
    checks: null,
    script: "print('generated detector')",
    ...overrides,
  }
}

function mount({
  runs = [],
  model = true,
  startError = "",
  empty = false,
}: {
  runs?: PentestDetail[]
  model?: boolean
  startError?: string
  empty?: boolean
} = {}) {
  const records = new Map(runs.map((run) => [run.run_id, run]))
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    let body: unknown
    if (url.startsWith("/api/intel/items?")) body = empty ? [] : [item]
    else if (url.startsWith("/api/intel/items/")) body = item
    else if (url === "/api/pentest/runs" && init?.method === "POST") {
      if (startError)
        return new Response(JSON.stringify({ detail: startError }), { status: 409 })
      const started = makeRun({
        status: "running",
        config: JSON.parse(String(init.body)),
        artifacts_ready: false,
        analysis: null,
        script: null,
        message: "正在分析所选情报",
      })
      records.set(started.run_id, started)
      body = started
    } else if (url.endsWith("/stop") && init?.method === "POST") {
      const stopped = makeRun({
        ...records.get("pentest_test"),
        status: "cancelling",
        artifacts_ready: false,
      })
      records.set(stopped.run_id, stopped)
      body = stopped
    } else if (url === "/api/pentest/overview")
      body = {
        active:
          [...records.values()].find((run) =>
            ["running", "cancelling"].includes(run.status)
          ) ?? null,
        run_count: records.size,
        script_count: [...records.values()].filter((r) => r.artifacts_ready).length,
        llm_available: model,
        model: "test-model",
      }
    else if (url === "/api/pentest/runs") body = [...records.values()]
    else body = records.get(url.split("/").at(-1) || "")
    return new Response(JSON.stringify(body))
  })
  vi.stubGlobal("fetch", fetchMock)
  render(
    <SWRConfig
      value={{
        provider: () => new Map(),
        dedupingInterval: 0,
        shouldRetryOnError: false,
      }}
    >
      <Wp12DashboardContent />
    </SWRConfig>
  )
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.history.replaceState({}, "", "/")
})

describe("WP1-2 intelligence to detector", () => {
  it("selects real intel and submits its ID, focus and protocol", async () => {
    const request = mount()
    expect(screen.getByRole("button", { name: "生成漏洞测试脚本" })).toBeDisabled()
    fireEvent.click(await screen.findByRole("button", { name: /系统提示泄漏研究/ }))
    await screen.findByText("采集的完整原文")
    fireEvent.change(screen.getByLabelText("测试重点（可选）"), {
      target: { value: "合成秘密提取" },
    })
    fireEvent.change(screen.getByLabelText("接口类型"), { target: { value: "chat" } })
    fireEvent.click(screen.getByRole("button", { name: "生成漏洞测试脚本" }))
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/pentest/runs",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            intel_id: item.item_id,
            focus: "合成秘密提取",
            protocol: "chat",
          }),
        })
      )
    )
    expect(await screen.findByText("正在分析所选情报")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "下载完整检测包" })).not.toBeInTheDocument()
  })

  it("opens intel from a collector deep link and keeps history provenance separate", async () => {
    window.history.replaceState({}, "", `/?intel_id=${encodeURIComponent(item.item_id)}`)
    mount({ runs: [makeRun()] })
    expect(await screen.findByText("采集的完整原文")).toBeInTheDocument()
    expect(await screen.findByRole("link", { name: "下载完整检测包" })).toHaveAttribute(
      "href",
      "/api/pentest/runs/pentest_test/artifacts/bundle.zip"
    )
    expect(screen.getAllByText("历史任务对应的情报")).toHaveLength(2)
    expect(screen.getByText(/尚未测试真实目标/)).toBeInTheDocument()
    expect(screen.getByText("print('generated detector')")).toBeInTheDocument()
  })

  it("shows missing evidence without claiming a script exists", async () => {
    const run = makeRun({
      status: "needs_evidence",
      artifacts_ready: false,
      script: null,
    })
    run.analysis = {
      ...run.analysis!,
      disposition: "needs_evidence",
      missing_information: ["缺少具体触发端点"],
    }
    mount({ runs: [run] })
    expect(await screen.findByText("缺少具体触发端点")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "下载完整检测包" })).not.toBeInTheDocument()
  })

  it("blocks generation without configured model", async () => {
    mount({ model: false })
    fireEvent.click(await screen.findByRole("button", { name: /系统提示泄漏研究/ }))
    await screen.findByText("采集的完整原文")
    expect(screen.getByRole("button", { name: "生成漏洞测试脚本" })).toBeDisabled()
    expect(screen.getByRole("alert")).toHaveTextContent("模型凭据")
  })

  it("displays API conflicts and allows a user to stop the active job", async () => {
    const request = mount({
      runs: [makeRun({ status: "running", artifacts_ready: false, script: null })],
    })
    fireEvent.click(await screen.findByRole("button", { name: "停止生成" }))
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(
        "/api/pentest/runs/pentest_test/stop",
        expect.objectContaining({ method: "POST" })
      )
    )
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "停止生成" })).toBeDisabled()
    )
  })

  it("surfaces a failed start and an empty library", async () => {
    mount({ startError: "已有生成任务" })
    fireEvent.click(await screen.findByRole("button", { name: /系统提示泄漏研究/ }))
    await screen.findByText("采集的完整原文")
    fireEvent.click(screen.getByRole("button", { name: "生成漏洞测试脚本" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("已有生成任务")
  })

  it("explains an empty library", async () => {
    mount({ empty: true })
    expect(await screen.findByText(/没有匹配的情报/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "生成漏洞测试脚本" })).toBeDisabled()
  })
})
