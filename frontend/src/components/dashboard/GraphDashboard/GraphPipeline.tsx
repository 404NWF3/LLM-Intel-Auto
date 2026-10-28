"use client"
import Link from "next/link"
import { useState, type FormEvent } from "react"
import { ArrowUpRight, Database, Network, ShieldCheck } from "lucide-react"
import { useIntelOverview } from "@/lib/api/intel"
import {
  sandboxFetch,
  type SandboxCapabilities,
  type SandboxRun,
} from "@/lib/api/sandbox"
import base from "../IntelDashboard/IntelDashboard.module.css"
import s from "./GraphDashboard.module.css"

export function GraphPipeline({
  capabilities,
  busy,
  onStarted,
  onSelect,
}: {
  capabilities?: SandboxCapabilities
  busy: boolean
  onStarted: (run: SandboxRun) => void
  onSelect: (id: string) => void
}) {
  const intel = useIntelOverview()
  const [limit, setLimit] = useState(100)
  const [focus, setFocus] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  const graph = capabilities?.graph
  async function build(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError("")
    try {
      const run = await sandboxFetch<SandboxRun>("/api/sandbox/graph/build", {
        method: "POST",
        body: JSON.stringify({ limit, focus }),
      })
      onStarted(run)
    } catch (e) {
      setError(e instanceof Error ? e.message : "构建启动失败")
    } finally {
      setPending(false)
    }
  }
  return (
    <section className={s.pipeline} aria-label="情报到沙盒审计链路">
      <div className={s.pipelineHeading}>
        <span className={base.eyebrow}>INTELLIGENCE → KNOWLEDGE → ASSESSMENT</span>
        <span>从收集到验证，证据一路可追溯</span>
      </div>
      <div className={s.pipelineSteps}>
        <div>
          <Database size={19} />
          <span>
            <small>01 / 情报采集</small>
            <strong>{intel.data?.item_count ?? "—"} 条已采集情报</strong>
            <Link href="/dashboard/wp11">
              前往采集工作台 <ArrowUpRight size={12} />
            </Link>
          </span>
        </div>
        <div>
          <Network size={19} />
          <span>
            <small>02 / 构建 GraphRAG</small>
            <strong>
              {graph?.status === "ready"
                ? `${graph.indexed_items} 条入图 · ${graph.counts.entities} 个实体`
                : "等待构建情报知识图谱"}
            </strong>
            <p>
              {graph?.status === "ready"
                ? `${graph.counts.relationships} 条关系 · ${graph.counts.community_reports} 份社区报告`
                : "抽取实体关系，再生成社区报告"}
            </p>
          </span>
        </div>
        <div>
          <ShieldCheck size={19} />
          <span>
            <small>03 / 沙盒审计</small>
            <strong>
              {capabilities?.case_ready ? "图谱已接入沙盒取证" : "构建完成后自动接入"}
            </strong>
            <Link href="/dashboard/wp13">
              前往沙盒审计工作台 <ArrowUpRight size={12} />
            </Link>
          </span>
        </div>
      </div>
      <form className={s.graphForm} onSubmit={build}>
        <label className={base.label}>
          入图关键词
          <input
            value={focus}
            maxLength={200}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="留空使用全部方向，如 prompt injection"
            disabled={busy || pending}
          />
        </label>
        <label className={base.label}>
          最多入图条数
          <input
            type="number"
            min={2}
            max={2000}
            required
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            disabled={busy || pending}
          />
        </label>
        <button
          className={base.start}
          disabled={busy || pending || !capabilities?.graph_build_ready}
        >
          {pending ? "正在准备语料…" : graph ? "更新情报图谱" : "从情报构建图谱"}
          <ArrowUpRight size={15} />
        </button>
      </form>
      <div className={s.graphFoot}>
        <p>
          按相关性与时间选取已采集摘要。构建会调用模型；成功验证后启用新索引，失败时保留原索引。
        </p>
        {graph?.run_id && (
          <button onClick={() => onSelect(graph.run_id)}>查看构建报告与来源 ↗</button>
        )}
      </div>
      {graph?.status === "ready" && (
        <p className={s.graphMeta}>
          最近构建 {new Date(graph.built_at).toLocaleString("zh-CN")} ·{" "}
          {graph.selection.focus || "全部方向"} · GraphRAG 社区全局检索
        </p>
      )}
      {error && (
        <p className={base.error} role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
