import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { ResearchDataset, ResearchRun } from "@/lib/api/researcher"
import { ResearcherDashboard } from "./index"

const dataset: ResearchDataset = {
  dataset_id: "demo-1", name: "demo.csv", rows: 300,
  columns: ["x1", "x2", "label"], numeric_columns: ["x1", "x2", "label"], suggested_label: "label",
}

function makeRun(overrides: Partial<ResearchRun> = {}): ResearchRun {
  return {
    run_id: "run-1", status: "succeeded", created_at: "2026-10-26T01:00:00Z",
    updated_at: "2026-10-26T01:00:05Z", dataset,
    config: { dataset_id: dataset.dataset_id, label_column: "label", max_rounds: 6, use_llm: true },
    current_round: 1, best_round: 1, metric: "validation_ap",
    rounds: [{ round: 1, model: "isolation_forest", params: { n_estimators: 100 },
      reason: "建立初始比较基线", planner: "baseline", score: 0.8123,
      status: "keep", duration_seconds: 0.4, error: null }],
    evaluation_note: "最终测试集未参与候选选择。", message: "建模已完成。",
    events: [], final_metrics: { ap: 0.7567, auroc: 0.9234 }, error: null,
    artifacts_ready: true, ...overrides,
  }
}

function mount({ runs = [], emptyDatasets = false, startError }: {
  runs?: ResearchRun[]; emptyDatasets?: boolean; startError?: string
} = {}) {
  const records = new Map(runs.map((run) => [run.run_id, run]))
  let available = emptyDatasets ? [] : [dataset]
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    let body: unknown
    if (url === "/api/researcher/datasets/demo" && init?.method === "POST") {
      available = [dataset]
      body = dataset
    } else if (url.startsWith("/api/researcher/datasets?") && init?.method === "POST") {
      const uploaded = { ...dataset, dataset_id: "uploaded-1", name: "uploaded.csv" }
      available = [uploaded]
      body = uploaded
    } else if (url === "/api/researcher/runs" && init?.method === "POST") {
      if (startError) return new Response(JSON.stringify({ detail: startError }), { status: 409 })
      const started = makeRun({ status: "running", rounds: [], best_round: null, artifacts_ready: false,
        final_metrics: null, config: JSON.parse(String(init.body)), message: "正在进行第 1 轮。" })
      records.set(started.run_id, started)
      return new Response(JSON.stringify(started), { status: 202 })
    } else if (url.endsWith("/stop") && init?.method === "POST") {
      const stopped = makeRun({ ...records.get("run-1"), status: "cancelling", message: "正在停止当前任务。" })
      records.set(stopped.run_id, stopped)
      body = stopped
    } else if (url === "/api/researcher/overview") {
      body = { active: [...records.values()].find((run) => ["running", "cancelling"].includes(run.status)) ?? null,
        run_count: records.size, llm_available: false, model: "configured-model" }
    } else if (url === "/api/researcher/datasets") body = available
    else if (url === "/api/researcher/runs") body = [...records.values()]
    else body = records.get(decodeURIComponent(url.split("/").at(-1) ?? ""))
    return new Response(JSON.stringify(body))
  })
  vi.stubGlobal("fetch", fetchMock)
  render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    <ResearcherDashboard />
  </SWRConfig>)
  return fetchMock
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe("ResearcherDashboard", () => {
  it("loads demo data and starts a bounded run without LLM calls", async () => {
    const fetchMock = mount({ emptyDatasets: true })
    fireEvent.click(screen.getByRole("button", { name: "使用演示数据" }))
    await screen.findByRole("option", { name: "demo.csv" })
    expect(screen.getByLabelText("异常标签列")).toHaveValue("label")
    fireEvent.change(screen.getByLabelText("最大轮次"), { target: { value: "3" } })
    fireEvent.click(screen.getByLabelText("使用大模型提出候选"))
    fireEvent.click(screen.getByRole("button", { name: "开始建模" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/researcher/runs",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ dataset_id: "demo-1",
        label_column: "label", max_rounds: 3, use_llm: false }) })))
    expect(await screen.findByText("正在进行第 1 轮。")).toBeInTheDocument()
  })

  it("uploads a raw CSV body and rejects an oversized file before sending it", async () => {
    const fetchMock = mount({ emptyDatasets: true })
    const file = new File(["x1,x2,label\n1,2,0"], "uploaded.csv", { type: "text/csv" })
    fireEvent.change(screen.getByLabelText("上传 CSV 文件"), { target: { files: [file] } })
    await screen.findByRole("option", { name: "uploaded.csv" })
    expect(fetchMock).toHaveBeenCalledWith("/api/researcher/datasets?filename=uploaded.csv",
      expect.objectContaining({ method: "POST", headers: { "Content-Type": "text/csv" }, body: file }))
    const oversized = new File(["x"], "large.csv")
    Object.defineProperty(oversized, "size", { value: 8 * 1024 * 1024 + 1 })
    fireEvent.change(screen.getByLabelText("上传 CSV 文件"), { target: { files: [oversized] } })
    expect(await screen.findByRole("alert")).toHaveTextContent("CSV 文件不能超过 8 MiB")
    expect(fetchMock.mock.calls.some(([url]) => url.includes("large.csv"))).toBe(false)
  })

  it("shows the backend error when a run cannot start", async () => {
    mount({ startError: "已有建模任务运行中。" })
    await screen.findByRole("option", { name: "demo.csv" })
    fireEvent.click(screen.getByRole("button", { name: "开始建模" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("已有建模任务运行中。")
    expect(screen.queryByRole("button", { name: "停止任务" })).not.toBeInTheDocument()
  })

  it("keeps unlabeled stability distinct from accuracy and identifies rule fallback", async () => {
    const run = makeRun({ metric: "rank_stability", final_metrics: null,
      feature_columns: ["x1", "x2"], ignored_columns: ["label", "description"],
      config: { dataset_id: "demo-1", label_column: null, max_rounds: 6, use_llm: true },
      rounds: [{ ...makeRun().rounds[0]!, planner: "fallback", reason: "模型调用失败，使用规则候选。" }] })
    mount({ runs: [run] })
    expect(await screen.findByText("最佳排序稳定性")).toBeInTheDocument()
    expect(screen.getByText(/排序稳定性仅为参考，不代表检测准确率/)).toBeInTheDocument()
    expect(screen.getByText("规则回退")).toBeInTheDocument()
    expect(screen.getByLabelText("实际输入特征")).toHaveTextContent("实际使用 2 个特征；已忽略列：label、description")
    expect(screen.queryByLabelText("最终测试指标")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "下载模型" })).toHaveAttribute("href", "/api/researcher/runs/run-1/model")
  })

  it("separates test metrics from validation and switches to a historical run", async () => {
    mount({ runs: [makeRun(), makeRun({ run_id: "older-1", dataset: { ...dataset, name: "older.csv" } })] })
    expect(await screen.findByLabelText("最终测试指标")).toHaveTextContent("0.7567")
    expect(screen.getByText("最优验证 AP")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("tab", { name: /运行历史/ }))
    fireEvent.click(screen.getByRole("button", { name: /older.csv/ }))
    await waitFor(() => expect(screen.getByRole("link", { name: "下载异常分数" }))
      .toHaveAttribute("href", "/api/researcher/runs/older-1/scores"))
  })

  it("stops an active run and disables duplicate stop requests", async () => {
    const fetchMock = mount({ runs: [makeRun({ status: "running", final_metrics: null, artifacts_ready: false })] })
    fireEvent.click(await screen.findByRole("button", { name: "停止任务" }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/researcher/runs/run-1/stop",
      expect.objectContaining({ method: "POST" })))
    expect(await screen.findByRole("button", { name: "正在停止…" })).toBeDisabled()
    expect(screen.queryByRole("link", { name: "下载模型" })).not.toBeInTheDocument()
  })
})
