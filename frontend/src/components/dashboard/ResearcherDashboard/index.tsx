"use client"

import { useRef, useState } from "react"
import type { ChangeEvent, FormEvent } from "react"
import { ArrowRight, Download, FlaskConical, RefreshCw, Square, Upload } from "lucide-react"
import useSWR from "swr"
import {
  isResearchActive,
  RESEARCH_MODEL_NAMES,
  RESEARCH_STATUS_NAMES,
  researchArtifactUrl,
  researcherFetch,
  uploadResearchDataset,
  useResearcherOverview,
} from "@/lib/api/researcher"
import type { ResearchDataset, ResearchRun } from "@/lib/api/researcher"
import base from "../IntelDashboard/IntelDashboard.module.css"
import s from "./ResearcherDashboard.module.css"

const scoreText = (value?: number | null) =>
  value == null || !Number.isFinite(value) ? "—" : value.toFixed(4)

function dateText(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false })
}

export function ResearcherDashboard() {
  const overview = useResearcherOverview()
  const datasets = useSWR<ResearchDataset[], Error>("/api/researcher/datasets", researcherFetch)
  const history = useSWR<ResearchRun[], Error>("/api/researcher/runs", researcherFetch, {
    refreshInterval: 4000,
  })
  const [datasetSelection, setDatasetSelection] = useState<ResearchDataset | null>(null)
  const [labelColumn, setLabelColumn] = useState<string | undefined>()
  const [maxRounds, setMaxRounds] = useState(6)
  const [useLlm, setUseLlm] = useState(true)
  const [selection, setSelection] = useState<string | null>(null)
  const [tab, setTab] = useState<"rounds" | "history">("rounds")
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [actionError, setActionError] = useState("")
  const fileInput = useRef<HTMLInputElement>(null)
  const dataset = datasetSelection ?? datasets.data?.[0]
  const selectedLabel = labelColumn ?? dataset?.suggested_label ?? ""
  const runId = selection ?? overview.data?.active?.run_id ?? history.data?.[0]?.run_id
  const detail = useSWR<ResearchRun, Error>(
    runId ? `/api/researcher/runs/${encodeURIComponent(runId)}` : null,
    researcherFetch,
    { refreshInterval: (run) => (isResearchActive(run) ? 2500 : 0) }
  )
  const current =
    detail.data ??
    history.data?.find((run) => run.run_id === runId) ??
    (overview.data?.active?.run_id === runId ? overview.data?.active : null)
  const busy = submitting || uploading || isResearchActive(overview.data?.active)
  const best = current?.rounds.find((round) => round.round === current.best_round)
  const unlabeled = current?.metric === "rank_stability" || current?.config.label_column === null
  const datasetOptions = datasetSelection && !datasets.data?.some(
    (item) => item.dataset_id === datasetSelection.dataset_id
  ) ? [datasetSelection, ...(datasets.data ?? [])] : datasets.data ?? []

  function refresh() {
    void overview.mutate()
    void datasets.mutate()
    void history.mutate()
    void detail.mutate()
  }

  async function addDataset(file?: File) {
    setUploading(true)
    setActionError("")
    try {
      const added = file
        ? await uploadResearchDataset(file)
        : await researcherFetch<ResearchDataset>("/api/researcher/datasets/demo", { method: "POST" })
      setDatasetSelection(added)
      setLabelColumn(added.suggested_label ?? "")
      void datasets.mutate()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "数据加载失败，请重试。")
    } finally {
      setUploading(false)
    }
  }

  function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (file) void addDataset(file)
  }

  async function start(event: FormEvent) {
    event.preventDefault()
    if (!dataset || busy) return
    setSubmitting(true)
    setActionError("")
    try {
      const run = await researcherFetch<ResearchRun>("/api/researcher/runs", {
        method: "POST",
        body: JSON.stringify({
          dataset_id: dataset.dataset_id,
          label_column: selectedLabel || null,
          max_rounds: maxRounds,
          use_llm: useLlm,
        }),
      })
      setSelection(run.run_id)
      setTab("rounds")
      void overview.mutate()
      void history.mutate()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "启动失败，请重试。")
    } finally {
      setSubmitting(false)
    }
  }

  async function stop() {
    if (!current || current.status !== "running" || stopping) return
    setStopping(true)
    setActionError("")
    try {
      const run = await researcherFetch<ResearchRun>(
        `/api/researcher/runs/${encodeURIComponent(current.run_id)}/stop`, { method: "POST" }
      )
      await detail.mutate(run, { revalidate: false })
      void overview.mutate()
      void history.mutate()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "停止失败，请重试。")
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className={base.page}>
      <header className={base.header}>
        <div>
          <span className={base.eyebrow}>MODEL RESEARCHER / 04</span>
          <h1>异常检测建模工作台<span className={base.titleDot}>.</span></h1>
          <p>给定数据，逐轮比较模型与参数，保留表现更好的方案。</p>
        </div>
        <div className={base.headerActions}>
          <span className={`${base.connection} ${overview.error ? base.offline : ""}`}>
            <i />
            {overview.error ? "连接异常" : !overview.data ? "正在连接" : overview.data.active ? "正在建模" : "服务已连接"}
          </span>
          <button type="button" className={base.iconButton} aria-label="刷新建模数据" onClick={refresh}>
            <RefreshCw size={17} />
          </button>
        </div>
      </header>

      {overview.error && <p className={base.error} role="alert">无法连接建模服务，请稍后刷新重试。</p>}
      {actionError && <p className={base.error} role="alert">{actionError}</p>}

      <div className={s.workspace}>
        <section className={base.control} aria-labelledby="research-form-title">
          <div className={base.sectionHeading}>
            <div className={base.iconTile}><FlaskConical size={20} /></div>
            <div><h2 id="research-form-title">开始一次建模</h2><p>数据 → 候选 → 评估 → 保留</p></div>
          </div>
          <form onSubmit={start}>
            <fieldset disabled={busy} className={base.fieldset}>
              <input ref={fileInput} type="file" accept=".csv,text/csv" className={base.srOnly}
                aria-label="上传 CSV 文件" onChange={onUpload} tabIndex={-1} />
              <div className={s.dataActions}>
                <button type="button" className={s.secondary} onClick={() => fileInput.current?.click()}>
                  <Upload size={14} />上传 CSV
                </button>
                <button type="button" className={s.secondary} onClick={() => void addDataset()}>使用演示数据</button>
              </div>
              <p className={s.hint}>{uploading ? "正在载入数据…" : "CSV 最大 8 MiB，30–10,000 行，1–100 个数值特征。"}</p>
              {datasets.error && <p className={s.inlineError} role="alert">{datasets.error.message}</p>}
              <label className={base.label} htmlFor="research-dataset">数据集</label>
              <select id="research-dataset" className={s.select} value={dataset?.dataset_id ?? ""}
                onChange={(event) => {
                  const selected = datasetOptions.find((item) => item.dataset_id === event.target.value)
                  if (selected) {
                    setDatasetSelection(selected)
                    setLabelColumn(selected.suggested_label ?? "")
                  }
                }}>
                {!dataset && <option value="">先上传 CSV 或使用演示数据</option>}
                {datasetOptions.map((item) => <option value={item.dataset_id} key={item.dataset_id}>{item.name}</option>)}
              </select>
              {dataset && <p className={s.hint}>{dataset.rows.toLocaleString()} 行 · {dataset.numeric_columns.length} 个数值列</p>}
              <label className={base.label} htmlFor="research-label">异常标签列</label>
              <select id="research-label" className={s.select} value={selectedLabel} disabled={!dataset}
                onChange={(event) => setLabelColumn(event.target.value)}>
                <option value="">无标签（常见标签列不作为特征）</option>
                {dataset?.columns.map((column) => <option value={column} key={column}>{column}</option>)}
              </select>
              <p className={s.hint}>{selectedLabel ? "标签须为 0（正常）和 1（异常），每类至少 5 行；标签不作为输入特征。" : "无标签时比较排序稳定性，它不代表检测准确率；常见标签列会从特征中排除。"}</p>
              <label className={base.label}>最大轮次
                <input type="number" min={1} max={20} required value={Number.isNaN(maxRounds) ? "" : maxRounds}
                  onChange={(event) => setMaxRounds(event.target.valueAsNumber)} />
              </label>
              <label className={s.checkbox}>
                <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
                使用大模型提出候选
              </label>
              <p className={s.hint}>
                {!useLlm ? "使用内置规则选择候选，无需大模型调用。" : !overview.data ? "正在检查模型配置…" : overview.data.llm_available
                  ? `当前模型：${overview.data.model}。调用失败时使用规则回退。`
                  : "大模型尚未就绪，将使用规则回退完成建模。"}
              </p>
              <button type="submit" className={base.start} disabled={!dataset || busy || Boolean(overview.error)}>
                <FlaskConical size={16} />{submitting ? "正在启动…" : "开始建模"}<ArrowRight size={16} />
              </button>
            </fieldset>
          </form>
          {overview.data?.active && <p className={s.notice}>已有建模任务运行中，完成或停止后可发起下一次。</p>}
        </section>

        <div className={s.right}>
          <section className={base.results} aria-labelledby="research-result-title">
            <div className={s.sectionHeader}>
              <div><h2 id="research-result-title">本次结果</h2><p>{current?.dataset.name ?? "等待第一轮实验"}</p></div>
              {current && <span className={base.runBadge}>{RESEARCH_STATUS_NAMES[current.status]}</span>}
            </div>
            {detail.error && <p className={s.inlineError} role="alert">任务详情加载失败：{detail.error.message}</p>}
            {current ? <>
              <div className={s.summary}>
                <div><span>已完成轮次</span><strong>{current.rounds.length}<small> / {current.config.max_rounds}</small></strong></div>
                <div><span>{unlabeled ? "最佳排序稳定性" : "最优验证 AP"}</span><strong>{scoreText(best?.score)}</strong></div>
                <div><span>当前保留模型</span><strong className={s.modelName}>{best ? RESEARCH_MODEL_NAMES[best.model] : "等待评估"}</strong></div>
              </div>
              <div className={s.resultBody}>
                <p className={s.message} aria-live="polite">{current.message}</p>
                {current.feature_columns && <p className={s.hint} aria-label="实际输入特征">
                  实际使用 {current.feature_columns.length} 个特征
                  {current.ignored_columns?.length ? `；已忽略列：${current.ignored_columns.join("、")}` : ""}。
                </p>}
                {!current.feature_columns && Boolean(current.ignored_columns?.length) &&
                  <p className={s.hint}>已忽略列：{current.ignored_columns?.join("、")}。</p>}
                {unlabeled && <p className={s.notice}>当前没有异常标签：排序稳定性仅为参考，不代表检测准确率，也不能证明模型发现了真实异常。</p>}
                {current.evaluation_note && <p className={s.hint}>{current.evaluation_note}</p>}
                {current.final_metrics && <div className={s.finalMetrics} aria-label="最终测试指标">
                  <span>最终测试 AP <strong>{scoreText(current.final_metrics.ap)}</strong></span>
                  <span>最终测试 AUROC <strong>{scoreText(current.final_metrics.auroc)}</strong></span>
                </div>}
                {current.error && <p className={s.inlineError} role="alert">{current.error}</p>}
                <div className={s.resultActions}>
                  {isResearchActive(current) && <button className={s.secondary} type="button"
                    disabled={stopping || current.status === "cancelling"} onClick={() => void stop()}>
                    <Square size={13} />{stopping || current.status === "cancelling" ? "正在停止…" : "停止任务"}
                  </button>}
                  {current.artifacts_ready && <>
                    <a className={s.secondary} href={researchArtifactUrl(current.run_id, "model")} download><Download size={14} />下载模型</a>
                    <a className={s.secondary} href={researchArtifactUrl(current.run_id, "scores")} download><Download size={14} />下载异常分数</a>
                  </>}
                </div>
              </div>
            </> : <div className={s.empty}>
              <FlaskConical size={28} /><h3>从一份数据开始</h3>
              <p>上传 CSV 或使用演示数据。每轮模型、参数与评估结果都会保留在这里。</p>
            </div>}
          </section>

          <section className={base.results}>
            <div className={base.resultsHeader}>
              <div className={base.tabs} role="tablist" aria-label="建模记录">
                <button type="button" role="tab" id="research-rounds-tab" aria-controls="research-records" aria-selected={tab === "rounds"} onClick={() => setTab("rounds")}>逐轮实验</button>
                <button type="button" role="tab" id="research-history-tab" aria-controls="research-records" aria-selected={tab === "history"} onClick={() => setTab("history")}>运行历史<span>{history.data?.length ?? 0}</span></button>
              </div>
            </div>
            <div id="research-records" role="tabpanel" aria-labelledby={`research-${tab}-tab`}>
              {tab === "rounds" ? current?.rounds.length ? <div className={s.tableWrap}>
                <table className={s.table}>
                  <thead><tr><th>轮次 / 模型</th><th>{unlabeled ? "稳定性参考" : "验证 AP"}</th><th>结果</th></tr></thead>
                  <tbody>{current.rounds.map((round) => <tr key={round.round} className={current.best_round === round.round ? s.bestRow : ""}>
                    <td><div className={s.roundTitle}><strong>#{round.round} {RESEARCH_MODEL_NAMES[round.model]}</strong>
                      <span className={s.planner}>{round.planner === "llm" ? "大模型" : round.planner === "baseline" ? "基线" : "规则回退"}</span></div>
                      <code className={s.params}>{Object.entries(round.params).map(([key, value]) => `${key}=${value}`).join(" · ") || "默认参数"}</code>
                      <p>{round.reason}</p>{round.error && <p className={s.inlineError}>{round.error}</p>}
                    </td>
                    <td className={s.number}>{scoreText(round.score)}<small>{round.duration_seconds.toFixed(1)} 秒</small></td>
                    <td><span className={base.runBadge}>{round.status === "keep" ? "保留" : round.status === "discard" ? "未提升" : "失败"}</span>
                      {current.best_round === round.round && <small className={s.bestLabel}>当前最优</small>}</td>
                  </tr>)}</tbody>
                </table>
              </div> : <p className={s.emptyText}>尚无实验记录。任务启动后会自动更新。</p> : <>
                {history.error && <p className={s.inlineError} role="alert">{history.error.message}</p>}
                {!history.data?.length && <p className={s.emptyText}>尚无历史任务。</p>}
                {history.data?.map((run) => <button type="button" key={run.run_id}
                  className={`${base.historyRow} ${run.run_id === runId ? base.selected : ""}`}
                  onClick={() => { setSelection(run.run_id); setTab("rounds"); setActionError("") }}>
                  <span><strong>{run.dataset.name}</strong><small>{dateText(run.created_at)} · {run.run_id}</small></span>
                  <span className={base.runBadge}>{RESEARCH_STATUS_NAMES[run.status]}</span>
                </button>)}
              </>}
            </div>
          </section>

          {current && <details className={s.activity}>
            <summary>运行日志 <span>{current.events.length} 条 · {current.run_id}</span></summary>
            <div className={s.events}>
              {current.events.length ? current.events.map((event, index) => <div key={`${event.ts}-${index}`}>
                <time>{dateText(event.ts)}</time><span>{event.message}</span>
              </div>) : <p>暂无日志。</p>}
            </div>
          </details>}
        </div>
      </div>
    </div>
  )
}
