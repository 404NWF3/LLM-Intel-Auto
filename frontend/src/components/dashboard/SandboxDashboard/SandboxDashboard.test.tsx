import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SandboxDashboard } from "./index"

function mount(active = false, postStatus = 202, graphActive = false) {
  const run = {
    run_id: "audit-1",
    kind: "audit",
    status: "running",
    title: "sample-app",
    phase: "profiling",
    created_at: "2026-10-14T05:00:00Z",
    config: {},
    state: { findings: [], hypotheses: {}, agent_calls_used: 1, cost_usd_used: 0.1 },
    artifacts: [],
    events: [],
    logs: ["Starting audit"],
    can_resume: false,
  }
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST")
      return new Response(
        JSON.stringify(postStatus === 202 ? run : { detail: "已有沙盒任务运行中" }),
        { status: postStatus }
      )
    const body = url.endsWith("overview")
      ? {
          capabilities: {
            runtime_ready: true,
            model_ready: true,
            audit_ready: true,
            graph_build_ready: true,
            case_ready: false,
            graph_index_ready: false,
            graph_credentials_ready: false,
          },
          active_run_id: graphActive ? "graph-1" : active ? run.run_id : null,
          active_run_kind: graphActive ? "graph" : active ? "audit" : null,
          recent_run_count: active ? 1 : 0,
          recent_completed_count: 0,
        }
      : url.endsWith("/runs?workspace=sandbox")
        ? active
          ? [run]
          : []
        : run
    return new Response(JSON.stringify(body))
  })
  vi.stubGlobal("fetch", fetchMock)
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <SandboxDashboard />
    </SWRConfig>
  )
  return fetchMock
}
afterEach(() => vi.unstubAllGlobals())
describe("SandboxDashboard", () => {
  it("links to the independent graph workspace without embedding its controls", async () => {
    mount()
    await screen.findByText("服务已连接")
    expect(screen.queryByLabelText("入图关键词")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "从情报构建图谱" })
    ).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /管理情报知识图谱/ })).toHaveAttribute(
      "href",
      "/dashboard/graphrag"
    )
  })
  it("keeps active graph builds out of assessments and audit history", async () => {
    const fetchMock = mount(true, 202, true)
    await screen.findByText("sample-app")
    expect(screen.getByText(/GraphRAG 正在构建/)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "停止任务" })).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/sandbox/runs/graph-1",
      expect.anything()
    )
    fireEvent.click(screen.getByRole("tab", { name: "任务历史" }))
    expect(
      screen.getByRole("button", { name: /sample-app.*仓库审计/ })
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sandbox/runs?workspace=sandbox",
      expect.anything()
    )
  })
  it("submits target, authorization and bounded audit settings to the real route", async () => {
    const fetchMock = mount()
    await screen.findByText("服务已连接")
    fireEvent.change(screen.getByLabelText("本地仓库目录"), {
      target: { value: "/tmp/sample-app" },
    })
    fireEvent.change(screen.getByLabelText("授权记录"), {
      target: { value: "owned-project" },
    })
    fireEvent.change(screen.getByLabelText("智能体调用上限"), { target: { value: "8" } })
    fireEvent.click(screen.getByRole("button", { name: "开始对抗审计" }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sandbox/runs",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            kind: "audit",
            target_repo: "/tmp/sample-app",
            authorization_ref: "owned-project",
            goal: "审查该 LLM 应用的提示词边界、工具权限与数据泄露风险",
            request: "",
            max_rounds: 4,
            max_agent_calls: 8,
            max_cost_usd: 5,
            use_graphrag: true,
          }),
        })
      )
    )
    expect(await screen.findByText("sample-app")).toBeInTheDocument()
  })
  it("keeps case generation unavailable without a graph and fills intent templates", async () => {
    mount()
    await screen.findByText("服务已连接")
    fireEvent.click(screen.getByRole("button", { name: "离线攻击案例" }))
    fireEvent.click(screen.getByRole("button", { name: "工具劫持" }))
    expect((screen.getByLabelText("测试意图") as HTMLTextAreaElement).value).toContain(
      "工具劫持"
    )
    expect(screen.getByRole("button", { name: "生成离线案例" })).toBeDisabled()
    expect(screen.getByText(/案例生成需要 GraphRAG 索引/)).toBeInTheDocument()
  })
  it("stops the active job and exposes its real runtime log", async () => {
    const fetchMock = mount(true)
    fireEvent.click(await screen.findByRole("button", { name: "停止任务" }))
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sandbox/runs/audit-1/stop",
        expect.objectContaining({ method: "POST" })
      )
    )
    fireEvent.click(screen.getByRole("tab", { name: "运行记录" }))
    expect(screen.getByText("Starting audit")).toBeInTheDocument()
  })
  it("shows start failures without claiming a task was created", async () => {
    mount(false, 409)
    await screen.findByText("服务已连接")
    fireEvent.change(screen.getByLabelText("本地仓库目录"), {
      target: { value: "/tmp/sample-app" },
    })
    fireEvent.change(screen.getByLabelText("授权记录"), {
      target: { value: "owned-project" },
    })
    fireEvent.click(screen.getByRole("button", { name: "开始对抗审计" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("已有沙盒任务运行中")
  })
})
