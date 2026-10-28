"use client"
import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import {
  ArrowUpRight,
  CircleStop,
  Database,
  FileText,
  GitBranch,
  Network,
  RefreshCw,
} from "lucide-react"
import {
  sandboxFetch,
  useSandboxOverview,
  useSandboxRuns,
  type SandboxDetail,
} from "@/lib/api/sandbox"
import { GraphPipeline } from "./GraphPipeline"
import { TaskArtifacts } from "../TaskArtifacts"
import base from "../IntelDashboard/IntelDashboard.module.css"
import task from "../TaskArtifacts/TaskRun.module.css"
import s from "./GraphDashboard.module.css"

const statusLabels: Record<string, string> = {
  running: "构建中",
  cancelling: "正在停止",
  succeeded: "已完成",
  failed: "失败",
  interrupted: "已中断",
  cancelled: "已停止",
}
const phases: Record<string, string> = {
  preparing_graph: "准备情报语料",
  running: "启动构建环境",
  load_input_documents: "读取情报语料",
  create_base_text_units: "情报分块",
  create_final_documents: "保存来源文档",
  extract_graph: "抽取实体与关系",
  finalize_graph: "整理知识图谱",
  create_communities: "识别知识社区",
  create_final_text_units: "绑定情报证据",
  create_community_reports: "生成社区报告",
  validating_graph: "验证图谱检索",
  succeeded: "图谱已就绪",
  complete: "图谱已就绪",
  failed: "构建失败",
  interrupted: "构建中断",
  cancelled: "已停止",
  cancelling: "正在停止",
}
const steps = [
  "load_input_documents",
  "extract_graph",
  "create_communities",
  "create_community_reports",
  "validating_graph",
]

export function GraphDashboard() {
  const overview = useSandboxOverview()
  const history = useSandboxRuns("graph")
  const [selection, setSelection] = useState<string | null>(null)
  const [tab, setTab] = useState<"results" | "activity" | "history">("results")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  const logRef = useRef<HTMLPreElement>(null)
  const graphActive = overview.data?.active_run_kind === "graph"
  const activeRunId = graphActive ? overview.data?.active_run_id : null
  const runId = selection ?? activeRunId ?? history.data?.[0]?.run_id
  const detail = useSWR<SandboxDetail, Error>(
    runId ? `/api/sandbox/runs/${runId}` : null,
    sandboxFetch,
    { refreshInterval: 2500 }
  )
  const current = detail.data
  const cap = overview.data?.capabilities
  const graph = cap?.graph
  const busy = pending || Boolean(overview.data?.active_run_id)
  const refresh = () => {
    void overview.mutate()
    void history.mutate()
    void detail.mutate()
  }
  function selectRun(id: string) {
    setSelection(id)
    setTab("results")
    setError("")
  }
  async function stop() {
    if (!runId) return
    setPending(true)
    setError("")
    try {
      await sandboxFetch(`/api/sandbox/runs/${runId}/stop`, { method: "POST" })
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "停止失败，请重试")
    } finally {
      setPending(false)
    }
  }
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [current?.logs.length, runId, tab])

  return (
    <div className={base.page}>
      <header className={base.header}>
        <div>
          <span className={base.eyebrow}>INTELLIGENCE KNOWLEDGE / GRAPHRAG</span>
          <h1>
            GraphRAG 工作台<span className={base.titleDot}>.</span>
          </h1>
          <p>将分散的情报连接成知识，让安全验证有据可循。</p>
        </div>
        <div className={base.headerActions}>
          <span className={`${base.connection} ${overview.error ? base.offline : ""}`}>
            <i />
            {overview.error
              ? "连接异常"
              : !overview.data
                ? "正在连接"
                : activeRunId
                  ? "图谱构建中"
                  : "服务已连接"}
          </span>
          <button className={base.iconButton} aria-label="刷新图谱数据" onClick={refresh}>
            <RefreshCw size={17} />
          </button>
        </div>
      </header>
      {overview.error && (
        <p className={base.error} role="alert">
          图谱服务未连接，请在根目录启动 <code>uv run saads-api</code>。
        </p>
      )}
      {cap && !cap.graph_build_ready && (
        <p className={base.error} role="alert">
          {!cap.runtime_ready
            ? "图谱运行环境尚未安装，请运行 uv sync --project backend/red_team/runtime --frozen --group dev。"
            : "请在根目录 .env 配置 DeepSeek 模型与密钥。"}
        </p>
      )}
      <section className={base.metrics} aria-label="当前生效图谱">
        {[
          {
            label: "入图情报",
            value: graph?.indexed_items,
            note: "当前生效的情报语料",
            icon: Database,
          },
          {
            label: "知识实体",
            value: graph?.counts.entities,
            note: "从情报中提取的实体",
            icon: Network,
          },
          {
            label: "关联关系",
            value: graph?.counts.relationships,
            note: "可回溯的实体关联",
            icon: GitBranch,
          },
          {
            label: "社区报告",
            value: graph?.counts.community_reports,
            note: "供沙盒审计全局检索",
            icon: FileText,
          },
        ].map(({ label, value, note, icon: Icon }) => (
          <article className={base.metric} key={label}>
            <div>
              <span>{label}</span>
              <Icon size={17} />
            </div>
            <strong>{value ?? "—"}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>
      {overview.data?.active_run_id && !graphActive && (
        <p className={s.notice}>
          沙盒审计任务正在运行，完成后可构建图谱。
          <Link href="/dashboard/wp13">查看沙盒审计进度 ↗</Link>
        </p>
      )}
      <GraphPipeline
        capabilities={cap}
        busy={busy || Boolean(overview.error)}
        onSelect={selectRun}
        onStarted={(job) => {
          selectRun(job.run_id)
          refresh()
        }}
      />
      <section className={task.runPanel} aria-label="图谱构建进度">
        <div className={task.runHeading}>
          <div>
            <span className={base.eyebrow}>GRAPH BUILD</span>
            <h2>{current?.title || "等待构建情报图谱"}</h2>
          </div>
          <span className={task.status}>
            {current ? statusLabels[current.status] || current.status : "尚未开始"}
          </span>
        </div>
        <div className={task.runId}>
          {runId || "从已采集情报创建图谱，进度与来源记录会保存在这里。"}
        </div>
        <div className={task.steps}>
          {steps.map((phase, index) => (
            <span
              key={phase}
              className={
                current?.status === "succeeded" ||
                current?.graph_progress?.completed.includes(phase)
                  ? task.completeStep
                  : current?.phase === phase
                    ? task.activeStep
                    : ""
              }
            >
              <i>{String(index + 1).padStart(2, "0")}</i>
              {phases[phase]}
            </span>
          ))}
        </div>
        <div className={task.runStats}>
          <span>
            当前阶段
            <strong>{current ? phases[current.phase] || current.phase : "—"}</strong>
          </span>
          <span>
            本次入图<strong>{current?.graph_progress?.indexed_items ?? "—"}</strong>
          </span>
          <span>
            索引工作流
            <strong>
              {current?.graph_progress
                ? `${current.graph_progress.completed.length} / ${current.graph_progress.total}`
                : "—"}
            </strong>
          </span>
          <span>
            图谱实体<strong>{current?.graph_progress?.counts?.entities ?? "—"}</strong>
          </span>
        </div>
        <div className={task.actions}>
          <button
            type="button"
            onClick={() => {
              setSelection(null)
              setError("")
            }}
          >
            跟随最新构建 ↗
          </button>
          {current && activeRunId === runId && (
            <button
              disabled={pending || current.status === "cancelling"}
              onClick={() => void stop()}
            >
              <CircleStop size={14} />
              停止构建
            </button>
          )}
        </div>
        {current?.error && <p className={s.notice}>{current.error}</p>}
        {(detail.error || error) && (
          <p className={base.error} role="alert">
            {error || `构建记录读取失败：${detail.error?.message}`}
          </p>
        )}
      </section>
      <section className={`${base.results} ${s.results}`}>
        <div className={base.resultsHeader}>
          <div className={base.tabs} role="tablist" aria-label="图谱任务视图">
            {(
              [
                ["results", "报告与来源"],
                ["activity", "构建日志"],
                ["history", "构建历史"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {tab === "results" && (
          <div role="tabpanel" aria-label="报告与来源">
            {current ? (
              <TaskArtifacts key={current.run_id} run={current} />
            ) : (
              <div className={base.empty}>
                <Network size={32} />
                <h3>从情报中发现关联</h3>
                <p>构建完成后，在这里查看图谱报告、入图来源与索引清单。</p>
              </div>
            )}
          </div>
        )}
        {tab === "activity" && (
          <div role="tabpanel" aria-label="构建日志">
            <div className={task.logLabel}>构建日志 · 最近 120 行</div>
            <pre ref={logRef} className={task.logs}>
              {current?.logs.join("\n") || "等待构建事件…"}
            </pre>
            {current?.events.map((event, index) => (
              <details className={task.event} key={index}>
                <summary>构建事件 · {String(event.data.event || index + 1)}</summary>
                <pre>{JSON.stringify(event.data, null, 2)}</pre>
              </details>
            ))}
          </div>
        )}
        {tab === "history" && (
          <div role="tabpanel" aria-label="构建历史">
            {history.error ? (
              <p className={base.error} role="alert">
                构建历史读取失败
              </p>
            ) : !history.data?.length ? (
              <p className={base.empty}>还没有图谱构建记录。</p>
            ) : (
              history.data.map((run) => (
                <button
                  className={`${base.historyRow} ${runId === run.run_id ? base.selected : ""}`}
                  key={run.run_id}
                  onClick={() => selectRun(run.run_id)}
                >
                  <span>
                    <strong>{run.title}</strong>
                    <small>
                      {new Date(run.created_at).toLocaleString("zh-CN")} · 图谱构建
                    </small>
                  </span>
                  <span className={base.runBadge}>
                    {statusLabels[run.status] || run.status}
                  </span>
                  <ArrowUpRight size={16} />
                </button>
              ))
            )}
          </div>
        )}
      </section>
      <footer className={base.footer}>
        SAADS KNOWLEDGE<span>情报 · 实体 · 关系 · 证据</span>
      </footer>
    </div>
  )
}
