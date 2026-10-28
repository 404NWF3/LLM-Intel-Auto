import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import { GraphDashboard } from "./index"

function mount({
  active = null,
  saved = false,
  postStatus = 202,
}: {
  active?: "graph" | "audit" | null
  saved?: boolean
  postStatus?: number
} = {}) {
  const run = {
    run_id: "graph-1",
    kind: "graph",
    status: active === "graph" ? "running" : "succeeded",
    title: "Prompt injection 知识图谱",
    phase: active === "graph" ? "extract_graph" : "succeeded",
    created_at: "2026-10-14T05:00:00Z",
    config: {},
    graph_progress: {
      phase: "extract_graph",
      completed: ["load_input_documents"],
      total: 8,
      indexed_items: 20,
    },
    state: {},
    artifacts: saved
      ? [{ name: "report.md", path: "results/graph/report.md", size: 50 }]
      : [],
    events: [],
    logs: ["Extracting intelligence entities"],
    can_resume: false,
  }
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST")
      return new Response(
        JSON.stringify(postStatus === 202 ? run : { detail: "没有匹配的情报" }),
        { status: postStatus }
      )
    if (url.includes("/artifact?"))
      return new Response("# Graph source report\nEvidence from collected intelligence.")
    const body =
      url === "/api/intel/overview"
        ? { item_count: 123 }
        : url.endsWith("overview")
          ? {
              capabilities: {
                runtime_ready: true,
                model_ready: true,
                graph_build_ready: true,
                case_ready: saved,
                graph_index_ready: saved,
                graph: null,
              },
              active_run_id: active ? `${active}-1` : null,
              active_run_kind: active,
            }
          : url === "/api/sandbox/runs?workspace=graph"
            ? saved || active === "graph"
              ? [run]
              : []
            : run
    return new Response(JSON.stringify(body))
  })
  vi.stubGlobal("fetch", fetchMock)
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <GraphDashboard />
    </SWRConfig>
  )
  return fetchMock
}
afterEach(() => vi.unstubAllGlobals())
describe("GraphDashboard", () => {
  it("builds a graph from selected intelligence and links the two agent workspaces", async () => {
    const fetchMock = mount()
    await screen.findByText("123 条已采集情报")
    fireEvent.change(screen.getByLabelText("入图关键词"), {
      target: { value: "prompt injection" },
    })
    fireEvent.change(screen.getByLabelText("最多入图条数"), { target: { value: "20" } })
    fireEvent.click(screen.getByRole("button", { name: "从情报构建图谱" }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sandbox/graph/build",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ limit: 20, focus: "prompt injection" }),
        })
      )
    )
    expect(await screen.findByText("Prompt injection 知识图谱")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /前往采集工作台/ })).toHaveAttribute(
      "href",
      "/dashboard/wp11"
    )
    expect(screen.getByRole("link", { name: /前往沙盒审计工作台/ })).toHaveAttribute(
      "href",
      "/dashboard/wp13"
    )
  })
  it("shows the existing graph report, sources, build log and graph-only history", async () => {
    const fetchMock = mount({ saved: true })
    expect(
      await screen.findByRole("heading", { name: "Graph source report" })
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "下载" })).toHaveAttribute(
      "href",
      "/api/sandbox/runs/graph-1/artifact?path=results%2Fgraph%2Freport.md"
    )
    fireEvent.click(screen.getByRole("tab", { name: "构建日志" }))
    expect(screen.getByText("Extracting intelligence entities")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("tab", { name: "构建历史" }))
    expect(
      screen.getByRole("button", { name: /Prompt injection 知识图谱.*图谱构建/ })
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sandbox/runs?workspace=graph",
      expect.anything()
    )
  })
  it("stops an active graph build", async () => {
    const fetchMock = mount({ active: "graph" })
    fireEvent.click(await screen.findByRole("button", { name: "停止构建" }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sandbox/runs/graph-1/stop",
        expect.objectContaining({ method: "POST" })
      )
    )
  })
  it("does not select an active audit or allow a conflicting graph build", async () => {
    const fetchMock = mount({ active: "audit" })
    await screen.findByText(/沙盒审计任务正在运行/)
    expect(screen.getByRole("button", { name: "从情报构建图谱" })).toBeDisabled()
    expect(screen.getByText("等待构建情报图谱")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "停止构建" })).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/sandbox/runs/audit-1",
      expect.anything()
    )
  })
  it("reports build errors without showing a created graph", async () => {
    mount({ postStatus: 422 })
    await screen.findByText("服务已连接")
    fireEvent.click(screen.getByRole("button", { name: "从情报构建图谱" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("没有匹配的情报")
    expect(screen.getByText("等待构建情报图谱")).toBeInTheDocument()
  })
})
